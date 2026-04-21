from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse

from app.competitors import _normalize_domain
from app.competitors import search_serp_urls
from app.features import build_features
from app.ml.model import FEATURE_COLUMNS
from app.parser import fetch_page
from app.serp import SerpConfigurationError, SerpProviderError, search as search_serp

import httpx


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_DATASET_PATH = DATA_DIR / "training_dataset.csv"
DEFAULT_FAILURES_PATH = DATA_DIR / "training_failures.csv"
DEFAULT_SEEDS_PATH = DATA_DIR / "training_query_seeds.csv"
DEFAULT_QUERIES_PATH = DATA_DIR / "training_queries.txt"
DEFAULT_CHECKPOINT_PATH = DATA_DIR / "training_dataset.checkpoint.json"

DATASET_COLUMNS = [
    "query",
    "category",
    "intent",
    "city",
    "region_code",
    "url",
    "domain",
    "rank",
    "serp_page",
    "title",
    "snippet",
    "page_type",
    "fetch_status",
    "fetch_error",
    "target_score",
] + FEATURE_COLUMNS

FAILURE_COLUMNS = [
    "query",
    "category",
    "intent",
    "city",
    "region_code",
    "url",
    "domain",
    "rank",
    "serp_page",
    "title",
    "snippet",
    "page_type",
    "fetch_status",
    "fetch_error",
    "target_score",
]


@dataclass(slots=True)
class TrainingSeed:
    query: str
    category: str
    intent: str
    city: str
    region_code: int | None
    top_n: int
    pages_to_scan: int

    @property
    def max_rank(self) -> int:
        return max(1, self.top_n * self.pages_to_scan)

    @property
    def seed_key(self) -> str:
        return "|".join(
            [
                self.query,
                self.category,
                self.intent,
                self.city,
                str(self.region_code or ""),
                str(self.top_n),
                str(self.pages_to_scan),
            ]
        )


def infer_page_type(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "/").lower()
    if path in {"", "/"}:
        return "homepage"
    if any(token in path for token in ("blog", "article", "news", "post")):
        return "article"
    if any(token in path for token in ("product", "catalog", "shop", "item")):
        return "product"
    if any(token in path for token in ("service", "services", "solutions", "category")):
        return "category"
    return "content"


def rank_to_score(rank: int, top_n: int) -> float:
    if rank <= 1 or top_n <= 1:
        return 100.0
    clamped_rank = min(max(rank, 1), top_n)
    return round(((top_n - clamped_rank) / (top_n - 1)) * 100.0, 4)


def _parse_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default
    normalized = str(value).strip()
    if not normalized:
        return default
    return int(normalized)


def _seed_from_query(query: str, top_n: int) -> TrainingSeed:
    return TrainingSeed(
        query=query.strip().replace("\ufeff", ""),
        category="",
        intent="commercial",
        city="",
        region_code=None,
        top_n=top_n,
        pages_to_scan=1,
    )


def _load_queries_from_file(file_path: str | Path) -> list[str]:
    with Path(file_path).open("r", encoding="utf-8-sig") as file:
        return [line.strip().replace("\ufeff", "") for line in file if line.strip()]


def load_seed_rows(
    seeds_file: str | Path = DEFAULT_SEEDS_PATH,
    default_top_n: int = 10,
) -> list[TrainingSeed]:
    resolved_path = Path(seeds_file)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Seed file not found: {resolved_path}")

    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        seeds: list[TrainingSeed] = []
        for row in reader:
            query = str(row.get("query") or "").strip().replace("\ufeff", "")
            if not query:
                continue
            seeds.append(
                TrainingSeed(
                    query=query,
                    category=str(row.get("category") or "").strip(),
                    intent=str(row.get("intent") or "commercial").strip() or "commercial",
                    city=str(row.get("city") or "").strip(),
                    region_code=_parse_int(row.get("region_code")),
                    top_n=_parse_int(row.get("top_n"), default_top_n) or default_top_n,
                    pages_to_scan=max(1, _parse_int(row.get("pages_to_scan"), 1) or 1),
                )
            )
    return seeds


def _slice_seed_rows(
    seeds: list[TrainingSeed],
    seed_offset: int = 0,
    seed_limit: int | None = None,
) -> list[TrainingSeed]:
    sliced = seeds[seed_offset:]
    if seed_limit is not None:
        sliced = sliced[:seed_limit]
    return sliced


def _page_key(seed: TrainingSeed, serp_page: int) -> str:
    return f"{seed.seed_key}|page={serp_page}"


def _row_key(query: str, url: str) -> str:
    return f"{query}|{url}"


def _read_existing_keys(csv_path: Path) -> set[str]:
    if not csv_path.exists():
        return set()
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return {
            _row_key(str(row.get("query") or ""), str(row.get("url") or ""))
            for row in reader
            if row.get("query") and row.get("url")
        }


def _load_checkpoint(checkpoint_path: Path) -> dict[str, set[str]]:
    if not checkpoint_path.exists():
        return {"completed_pages": set(), "written_keys": set()}

    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return {
        "completed_pages": set(payload.get("completed_pages", [])),
        "written_keys": set(payload.get("written_keys", [])),
    }


def _save_checkpoint(checkpoint_path: Path, completed_pages: set[str], written_keys: set[str]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "completed_pages": sorted(completed_pages),
        "written_keys": sorted(written_keys),
    }
    checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_rows(rows: list[dict[str, object]], output_path: Path, fieldnames: list[str]) -> None:
    if not rows:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if output_path.exists() else "w"
    with output_path.open(mode, encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)


def _base_row(seed: TrainingSeed, result: dict[str, object]) -> dict[str, object]:
    url = str(result.get("url") or "").strip()
    return {
        "query": seed.query,
        "category": seed.category,
        "intent": seed.intent,
        "city": seed.city,
        "region_code": seed.region_code or "",
        "url": url,
        "domain": _normalize_domain(url) or url,
        "rank": int(result.get("rank") or 0),
        "serp_page": int(result.get("serp_page") or 0),
        "title": str(result.get("title") or "").strip(),
        "snippet": str(result.get("snippet") or "").strip(),
        "page_type": infer_page_type(url),
        "target_score": rank_to_score(int(result.get("rank") or 1), seed.max_rank),
    }


def _process_search_result(seed: TrainingSeed, result: dict[str, object]) -> tuple[str, dict[str, object], bool]:
    row = _base_row(seed, result)
    url = str(row["url"])

    try:
        fetch_result = fetch_page(url, use_browser=True)
        if fetch_result["status"] != "success":
            raise RuntimeError(str(fetch_result.get("fetch_error_message") or fetch_result.get("fetch_error_code") or "fetch failed"))
        html = str(fetch_result.get("html") or "")
        text = str(fetch_result.get("text") or "")
        features = build_features(html=html, text=text, query=seed.query)
        success_row = {
            **row,
            "fetch_status": "ok",
            "fetch_error": "",
        }
        for feature_name in FEATURE_COLUMNS:
            success_row[feature_name] = float(features.get(feature_name, 0.0))
        return "success", success_row, not bool(text.strip())
    except Exception as error:
        failure_row = {
            **row,
            "fetch_status": "failed",
            "fetch_error": str(error)[:500],
        }
        return "failure", failure_row, False


def _fetch_seed_page(seed: TrainingSeed, serp_page: int) -> list[dict[str, object]]:
    try:
        results = search_serp(
            query=seed.query,
            top_n=seed.top_n,
            region_code=seed.region_code,
            page=serp_page,
        )
    except (SerpConfigurationError, SerpProviderError, httpx.HTTPError, ValueError):
        if serp_page > 0:
            return []
        fallback_urls = search_serp_urls(
            query=seed.query,
            limit=seed.top_n,
            unique_domains=False,
        )
        results = [
            {
                "url": url,
                "title": "",
                "snippet": "",
                "rank": index,
                "serp_page": 0,
            }
            for index, url in enumerate(fallback_urls, start=1)
        ]

    normalized_results: list[dict[str, object]] = []
    for index, result in enumerate(results, start=1):
        rank = int(result.get("rank") or (serp_page * seed.top_n + index))
        normalized_results.append(
            {
                "url": str(result.get("url") or "").strip(),
                "title": str(result.get("title") or "").strip(),
                "snippet": str(result.get("snippet") or "").strip(),
                "rank": rank,
                "serp_page": int(result.get("serp_page") or serp_page),
            }
        )
    return normalized_results


def build_dataset_for_query(
    query: str,
    top_n: int = 10,
    max_workers: int = 6,
    region_code: int | None = None,
) -> list[dict[str, object]]:
    seed = TrainingSeed(
        query=query.strip().replace("\ufeff", ""),
        category="",
        intent="commercial",
        city="",
        region_code=region_code,
        top_n=top_n,
        pages_to_scan=1,
    )
    results = _fetch_seed_page(seed, serp_page=0)
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process_search_result, seed, result) for result in results]
        for future in as_completed(futures):
            status, row, _empty_text = future.result()
            if status == "success":
                rows.append(row)
    return sorted(rows, key=lambda item: int(item["rank"]))


def build_dataset(
    queries: list[str] | None = None,
    top_n: int = 10,
    output_path: str | Path = DEFAULT_DATASET_PATH,
    failures_path: str | Path = DEFAULT_FAILURES_PATH,
    checkpoint_path: str | Path = DEFAULT_CHECKPOINT_PATH,
    seeds_file: str | Path = DEFAULT_SEEDS_PATH,
    overwrite: bool = False,
    max_workers: int = 6,
    query_delay_seconds: float = 1.0,
    seed_offset: int = 0,
    seed_limit: int | None = None,
) -> dict[str, object]:
    dataset_path = Path(output_path)
    failures_csv_path = Path(failures_path)
    checkpoint_json_path = Path(checkpoint_path)

    if overwrite:
        for path in (dataset_path, failures_csv_path, checkpoint_json_path):
            if path.exists():
                path.unlink()

    if queries:
        seeds = [_seed_from_query(query, top_n=top_n) for query in queries if query.strip()]
    else:
        seeds = load_seed_rows(seeds_file=seeds_file, default_top_n=top_n)
    seeds = _slice_seed_rows(seeds, seed_offset=seed_offset, seed_limit=seed_limit)

    checkpoint = _load_checkpoint(checkpoint_json_path)
    written_keys = checkpoint["written_keys"] | _read_existing_keys(dataset_path) | _read_existing_keys(failures_csv_path)
    completed_pages = checkpoint["completed_pages"]

    success_count = 0
    failure_count = 0
    empty_text_count = 0
    unique_domains: set[str] = set()
    unique_queries: set[str] = set()
    processed_seed_pages = 0

    for seed_index, seed in enumerate(seeds, start=1):
        if seed_index > 1 and query_delay_seconds > 0:
            time.sleep(query_delay_seconds)

        for serp_page in range(seed.pages_to_scan):
            current_page_key = _page_key(seed, serp_page)
            if current_page_key in completed_pages:
                continue

            raw_results = _fetch_seed_page(seed, serp_page=serp_page)
            raw_results = [
                result
                for result in raw_results
                if _row_key(seed.query, str(result.get("url") or "")) not in written_keys
            ]

            success_rows: list[dict[str, object]] = []
            failure_rows: list[dict[str, object]] = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_process_search_result, seed, result) for result in raw_results]
                for future in as_completed(futures):
                    status, row, is_empty_text = future.result()
                    written_keys.add(_row_key(str(row["query"]), str(row["url"])))
                    if status == "success":
                        success_rows.append(row)
                        unique_domains.add(str(row["domain"]))
                        unique_queries.add(str(row["query"]))
                        success_count += 1
                        if is_empty_text:
                            empty_text_count += 1
                    else:
                        failure_rows.append(row)
                        failure_count += 1

            success_rows.sort(key=lambda item: int(item["rank"]))
            failure_rows.sort(key=lambda item: int(item["rank"]))
            _write_rows(success_rows, dataset_path, DATASET_COLUMNS)
            _write_rows(failure_rows, failures_csv_path, FAILURE_COLUMNS)

            completed_pages.add(current_page_key)
            processed_seed_pages += 1
            _save_checkpoint(checkpoint_json_path, completed_pages=completed_pages, written_keys=written_keys)
            print(
                f"[{seed_index}/{len(seeds)}] query='{seed.query}' page={serp_page} "
                f"success={len(success_rows)} failures={len(failure_rows)} total_success={success_count}"
            )

    total_attempts = success_count + failure_count
    failure_rate = round((failure_count / total_attempts), 6) if total_attempts else 0.0
    empty_text_rate = round((empty_text_count / success_count), 6) if success_count else 0.0
    return {
        "dataset_path": str(dataset_path),
        "failures_path": str(failures_csv_path),
        "checkpoint_path": str(checkpoint_json_path),
        "seeds_count": len(seeds),
        "processed_seed_pages": processed_seed_pages,
        "rows_count": success_count,
        "failures_count": failure_count,
        "unique_queries": len(unique_queries),
        "unique_domains": len(unique_domains),
        "failure_rate": failure_rate,
        "empty_text_rate": empty_text_rate,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--queries-file", default="")
    parser.add_argument("--seeds-file", default=str(DEFAULT_SEEDS_PATH))
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--failures-output", default=str(DEFAULT_FAILURES_PATH))
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--query-delay", type=float, default=1.0)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--seed-limit", type=int, default=0)
    args = parser.parse_args()

    queries = list(args.query)
    if args.queries_file and Path(args.queries_file).exists():
        queries.extend(_load_queries_from_file(args.queries_file))

    try:
        result = build_dataset(
            queries=queries or None,
            top_n=args.top_n,
            output_path=args.output,
            failures_path=args.failures_output,
            checkpoint_path=args.checkpoint,
            seeds_file=args.seeds_file,
            overwrite=args.overwrite,
            max_workers=args.max_workers,
            query_delay_seconds=args.query_delay,
            seed_offset=args.seed_offset,
            seed_limit=args.seed_limit or None,
        )
        print(result)
    except SerpConfigurationError as error:
        print({"error": str(error)})
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
