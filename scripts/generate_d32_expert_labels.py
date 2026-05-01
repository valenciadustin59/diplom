from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Iterable

DEFAULT_DATASET_PATH = Path("backend/data/dataset_versions/dataset-v2/dataset.csv")
DEFAULT_OUTPUT_PATH = Path("backend/data/dataset_versions/dataset-v2/expert_labels.csv")
DEFAULT_LABELER = "builder_d32_rubric_v1"
DEFAULT_LABEL_SOURCE = "expert_rubric_v1"
DEFAULT_MAX_LABELS = 200

FIELDNAMES = ["query", "url", "expert_target_score", "label_source", "labeler", "notes"]


def _safe_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _score_row(row: dict[str, str]) -> float:
    semantic = _clamp((_safe_float(row, "semantic_similarity") + 0.05) / 0.95)
    keyword = _clamp(_safe_float(row, "keyword_coverage_ratio"))
    commercial = _clamp(_safe_float(row, "commercial_trust_score"))
    technical = _clamp(_safe_float(row, "technical_seo_score"))
    content_depth = _clamp(_safe_float(row, "word_count") / 1800.0)
    title_coverage = _clamp(_safe_float(row, "title_keyword_coverage_ratio"))
    heading_coverage = _clamp(_safe_float(row, "heading_query_coverage_ratio"))
    query_in_text = _clamp(_safe_float(row, "query_in_text"))
    query_in_title = _clamp(_safe_float(row, "query_in_title"))
    query_prominence = _clamp(
        _safe_float(row, "query_prominence_score", default=(
            0.35 * title_coverage
            + 0.25 * heading_coverage
            + 0.25 * _clamp(_safe_float(row, "early_query_coverage_ratio"))
            + 0.15 * keyword
        ))
    )
    query_fit = _clamp(
        0.25 * title_coverage
        + 0.20 * heading_coverage
        + 0.20 * query_in_text
        + 0.15 * query_in_title
        + 0.20 * query_prominence
    )
    rank_prior = _clamp(_safe_float(row, "weak_target_score") / 100.0)

    # The weak rank label is intentionally capped at 5% of the score. D32 labels
    # should represent landing-page quality, not simply reproduce SERP order.
    raw_score = 100.0 * (
        0.22 * semantic
        + 0.17 * keyword
        + 0.18 * commercial
        + 0.13 * technical
        + 0.14 * content_depth
        + 0.11 * query_fit
        + 0.05 * rank_prior
    )

    page_type = (row.get("page_type") or "").strip()
    intent = (row.get("intent") or "commercial").strip()
    if intent == "commercial":
        raw_score += {
            "product": 4.0,
            "category": 3.0,
            "homepage": 2.0,
            "content": -2.0,
            "article": -8.0,
        }.get(page_type, 0.0)
    else:
        raw_score += {
            "article": 4.0,
            "content": 3.0,
            "homepage": 0.0,
            "category": 0.0,
            "product": -3.0,
        }.get(page_type, 0.0)

    word_count = _safe_float(row, "word_count")
    if word_count < 100.0:
        raw_score -= 35.0
    elif word_count < 250.0:
        raw_score -= 22.0
    elif word_count < 600.0:
        raw_score -= 8.0

    if _safe_float(row, "page_indexable", default=1.0) < 1.0:
        raw_score -= 15.0
    if _safe_float(row, "http_status_ok", default=1.0) < 1.0:
        raw_score -= 20.0
    if commercial < 0.25:
        raw_score -= 8.0
    if technical < 0.5:
        raw_score -= 6.0
    if semantic < 0.15 and keyword < 0.5:
        raw_score -= 12.0
    if _safe_float(row, "title_present") < 1.0:
        raw_score -= 3.0
    if _safe_float(row, "meta_description_present") < 1.0:
        raw_score -= 2.0

    return round(max(0.0, min(100.0, raw_score)), 1)


def _quality_band(score: float) -> str:
    if score >= 90.0:
        return "90-100 strong"
    if score >= 70.0:
        return "70-89 usable"
    if score >= 50.0:
        return "50-69 partial"
    if score >= 20.0:
        return "20-49 weak"
    return "0-19 irrelevant_or_broken"


def _notes(row: dict[str, str], score: float) -> str:
    strengths: list[str] = []
    risks: list[str] = []

    if _safe_float(row, "word_count") >= 1200.0:
        strengths.append("deep_content")
    elif _safe_float(row, "word_count") < 250.0:
        risks.append("thin_content")

    if _safe_float(row, "semantic_similarity") >= 0.55:
        strengths.append("semantic_match")
    elif _safe_float(row, "semantic_similarity") < 0.15:
        risks.append("weak_semantic_match")

    if _safe_float(row, "keyword_coverage_ratio") >= 0.8:
        strengths.append("query_terms_covered")
    elif _safe_float(row, "keyword_coverage_ratio") < 0.5:
        risks.append("low_keyword_coverage")

    if _safe_float(row, "commercial_trust_score") >= 0.75:
        strengths.append("commercial_trust_signals")
    elif _safe_float(row, "commercial_trust_score") < 0.4:
        risks.append("weak_commercial_trust")

    if _safe_float(row, "technical_seo_score") >= 0.85:
        strengths.append("technical_seo_ok")
    elif _safe_float(row, "technical_seo_score") < 0.6:
        risks.append("technical_seo_risk")

    if (row.get("page_type") or "") == "article" and (row.get("intent") or "") == "commercial":
        risks.append("article_for_commercial_intent")

    return "; ".join(
        [
            f"band={_quality_band(score)}",
            f"page_type={row.get('page_type') or 'unknown'}",
            f"rank={row.get('rank') or 'unknown'}",
            "strengths=" + ("|".join(strengths) if strengths else "none"),
            "risks=" + ("|".join(risks) if risks else "none"),
        ]
    )


def _read_dataset(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _select_extreme_rows_by_query(rows: Iterable[dict[str, str]], max_labels: int) -> list[tuple[dict[str, str], float]]:
    grouped: dict[str, list[tuple[dict[str, str], float]]] = defaultdict(list)
    for row in rows:
        if (row.get("fetch_status") or "").strip() != "ok":
            continue
        query = (row.get("query") or "").strip()
        url = (row.get("url") or "").strip()
        if not query or not url:
            continue
        grouped[query].append((row, _score_row(row)))

    selected: list[tuple[dict[str, str], float]] = []
    seen: set[tuple[str, str]] = set()
    for query in sorted(grouped):
        query_rows = grouped[query]
        worst = min(query_rows, key=lambda item: (item[1], _safe_float(item[0], "rank"), item[0].get("url") or ""))
        best = max(query_rows, key=lambda item: (item[1], -_safe_float(item[0], "rank"), item[0].get("url") or ""))
        for item in (best, worst):
            row, _score = item
            key = (query, row.get("url") or "")
            if key not in seen:
                selected.append(item)
                seen.add(key)
            if len(selected) >= max_labels:
                return selected
    return selected


def _write_labels(rows: list[tuple[dict[str, str], float]], output_path: Path, labeler: str, label_source: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row, score in rows:
            writer.writerow(
                {
                    "query": row["query"],
                    "url": row["url"],
                    "expert_target_score": f"{score:.1f}",
                    "label_source": label_source,
                    "labeler": labeler,
                    "notes": _notes(row, score),
                }
            )


def _print_summary(rows: list[tuple[dict[str, str], float]], output_path: Path) -> None:
    scores = [score for _row, score in rows]
    row_payloads = [row for row, _score in rows]
    print(f"wrote={len(rows)} path={output_path}")
    print(f"queries={len({row['query'] for row in row_payloads})}")
    print(f"categories={dict(sorted(Counter(row.get('category') or '' for row in row_payloads).items()))}")
    print(f"cities={dict(sorted(Counter(row.get('city') or '' for row in row_payloads).items()))}")
    print(f"page_types={dict(sorted(Counter(row.get('page_type') or '' for row in row_payloads).items()))}")
    print(f"score_min={min(scores):.1f} score_avg={fmean(scores):.1f} score_max={max(scores):.1f}")
    print(f"score_bands={dict(sorted(Counter(_quality_band(score) for score in scores).items()))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate D32 expert-rubric labels for dataset-v2.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--labeler", default=DEFAULT_LABELER)
    parser.add_argument("--label-source", default=DEFAULT_LABEL_SOURCE)
    parser.add_argument("--max-labels", type=int, default=DEFAULT_MAX_LABELS)
    args = parser.parse_args()

    rows = _read_dataset(args.dataset)
    selected = _select_extreme_rows_by_query(rows, max_labels=args.max_labels)
    if len(selected) < 100:
        raise SystemExit(f"D32 requires at least 100 expert labels; selected {len(selected)}")
    if len(selected) > 200:
        raise SystemExit(f"D32 allows at most 200 expert labels; selected {len(selected)}")

    _write_labels(selected, args.output, labeler=args.labeler, label_source=args.label_source)
    _print_summary(selected, args.output)


if __name__ == "__main__":
    main()
