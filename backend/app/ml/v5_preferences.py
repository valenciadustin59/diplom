from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha1
import json
from pathlib import Path
import shutil
from statistics import fmean
from typing import Any, Mapping, Sequence

from app.ml.dataset_quality import (
    PRODUCTION_LIKE_DATASET_THRESHOLDS,
    DatasetQualityThresholds,
    save_dataset_manifest,
)
from app.ml.dataset_versions import BASELINE_DATASET_VERSION
from app.ml.top3_regression_analysis import DEFAULT_D50_REPORT_JSON_PATH
from app.ml.train import create_dataset_split
from app.ml.v3_dataset import DATASET_VERSIONS_DIR
from app.ml.v4_dataset import DEFAULT_PRODUCTION_ARTIFACT_PATH


DEFAULT_SOURCE_DATASET_DIR = DATASET_VERSIONS_DIR / "dataset-v4"
DEFAULT_SOURCE_DATASET_PATH = DEFAULT_SOURCE_DATASET_DIR / "dataset.csv"
DEFAULT_SOURCE_FAILURES_PATH = DEFAULT_SOURCE_DATASET_DIR / "failures.csv"
DEFAULT_SOURCE_SEEDS_PATH = DEFAULT_SOURCE_DATASET_DIR / "seeds.csv"
DEFAULT_SOURCE_ARTIFACTS_DIR = DATASET_VERSIONS_DIR / "dataset-v2" / "artifacts"
DEFAULT_OUTPUT_DIR = DATASET_VERSIONS_DIR / "dataset-v5"
DEFAULT_OUTPUT_DATASET_PATH = DEFAULT_OUTPUT_DIR / "dataset.csv"
DEFAULT_OUTPUT_FAILURES_PATH = DEFAULT_OUTPUT_DIR / "failures.csv"
DEFAULT_OUTPUT_SEEDS_PATH = DEFAULT_OUTPUT_DIR / "seeds.csv"
DEFAULT_OUTPUT_SPLIT_PATH = DEFAULT_OUTPUT_DIR / "split.json"
DEFAULT_OUTPUT_MANIFEST_PATH = DEFAULT_OUTPUT_DIR / "manifest.json"
DEFAULT_OUTPUT_PAGE_LABELS_PATH = DEFAULT_OUTPUT_DIR / "page_labels.csv"
DEFAULT_OUTPUT_PREFERENCE_LABELS_PATH = DEFAULT_OUTPUT_DIR / "preference_labels.csv"
DEFAULT_OUTPUT_SPLIT_VALIDATION_PATH = DEFAULT_OUTPUT_DIR / "d51-preference-split-validation.json"
DEFAULT_OUTPUT_REPORT_JSON_PATH = DEFAULT_OUTPUT_DIR / "d51-query-preference-label-report.json"
DEFAULT_OUTPUT_REPORT_MD_PATH = DEFAULT_OUTPUT_DIR / "d51-query-preference-label-report.md"

DEFAULT_DATASET_VERSION = "dataset-v5"
LABEL_SCHEMA_VERSION_V5 = "ranking-aware-v5"
PAGE_LABEL_SOURCE_V5 = "seo_weighted_page_quality_v5"
PREFERENCE_LABEL_SOURCE_V5 = "query_preference_rubric_v5"
DEFAULT_LABELER = "d51_query_preference_rubric_v1"

PAGE_LABEL_FIELDS = [
    "query",
    "url",
    "page_target_score",
    "ranking_target_score",
    "critical_search_score",
    "rank_prior_score",
    "quality_band",
    "d50_focus_query",
    "label_source",
    "labeler",
    "notes",
]
PREFERENCE_FIELDS = [
    "query",
    "winner_url",
    "loser_url",
    "preference_strength",
    "usable_for_training",
    "weight",
    "winner_page_score",
    "loser_page_score",
    "winner_ranking_target",
    "loser_ranking_target",
    "target_margin",
    "winner_rank",
    "loser_rank",
    "serp_rank_delta",
    "label_source",
    "labeler",
    "reason",
    "patterns",
    "d50_focus_query",
]


@dataclass(frozen=True, slots=True)
class PageLabel:
    query: str
    url: str
    page_target_score: float
    ranking_target_score: float
    critical_search_score: float
    rank_prior_score: float
    quality_band: str
    d50_focus_query: bool
    label_source: str
    labeler: str
    notes: str


@dataclass(frozen=True, slots=True)
class PreferenceLabel:
    query: str
    winner_url: str
    loser_url: str
    preference_strength: str
    usable_for_training: bool
    weight: float
    winner_page_score: float
    loser_page_score: float
    winner_ranking_target: float
    loser_ranking_target: float
    target_margin: float
    winner_rank: int
    loser_rank: int
    serp_rank_delta: int
    label_source: str
    labeler: str
    reason: str
    patterns: str
    d50_focus_query: bool


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def _score01(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    return max(0.0, min(1.0, _safe_float(row.get(key), default)))


def _read_csv_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return [], []
    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: str | Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha1(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_float(value: float, digits: int = 4) -> str:
    return str(round(float(value), digits))


def _rank_prior_score(row: Mapping[str, object]) -> float:
    rank = max(1, _safe_int(row.get("rank"), 10))
    return max(0.0, 100.0 - float(rank - 1) * 7.5)


def _critical_search_score(row: Mapping[str, object]) -> float:
    values = [
        _score01(row, "http_status_ok", 1.0),
        _score01(row, "page_indexable", 1.0),
        _score01(row, "canonical_signal_score"),
        _score01(row, "technical_seo_score"),
        _score01(row, "title_keyword_coverage_ratio"),
        _score01(row, "heading_query_coverage_ratio"),
        _score01(row, "semantic_similarity"),
        _score01(row, "query_semantic_alignment"),
        _score01(row, "keyword_coverage_ratio"),
        _score01(row, "intent_alignment_score"),
    ]
    return 100.0 * (sum(values) / len(values))


def _ranking_target_score(row: Mapping[str, object]) -> float:
    page_score = _safe_float(row.get("target_score"))
    rank_prior = _rank_prior_score(row)
    critical = _critical_search_score(row)
    return round(0.62 * page_score + 0.23 * rank_prior + 0.15 * critical, 4)


def _quality_band(score: float) -> str:
    if score >= 85.0:
        return "high"
    if score >= 65.0:
        return "medium"
    if score >= 40.0:
        return "low"
    return "blocked"


def _d50_focus_queries(d50_report: Mapping[str, Any]) -> set[str]:
    focus_queries: set[str] = set()
    for item in d50_report.get("suggested_d51_focus", []):
        if isinstance(item, dict) and item.get("area") == "query_level_preference_labels":
            focus_queries.update(str(query) for query in item.get("queries") or [] if str(query).strip())
    return focus_queries


def _d50_diagnostics_by_query(d50_report: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    diagnostics = d50_report.get("query_diagnostics") if isinstance(d50_report.get("query_diagnostics"), list) else []
    for diagnostic in diagnostics:
        if isinstance(diagnostic, dict) and str(diagnostic.get("query") or "").strip():
            grouped[str(diagnostic["query"])].append(diagnostic)
    return dict(grouped)


def build_page_labels(
    rows: Sequence[Mapping[str, str]],
    *,
    d50_focus_queries: set[str] | None = None,
    labeler: str = DEFAULT_LABELER,
) -> list[PageLabel]:
    focus_queries = d50_focus_queries or set()
    labels: list[PageLabel] = []
    for row in rows:
        page_score = round(_safe_float(row.get("target_score")), 4)
        ranking_target = _ranking_target_score(row)
        labels.append(
            PageLabel(
                query=str(row.get("query") or "").strip(),
                url=str(row.get("url") or "").strip(),
                page_target_score=page_score,
                ranking_target_score=ranking_target,
                critical_search_score=round(_critical_search_score(row), 4),
                rank_prior_score=round(_rank_prior_score(row), 4),
                quality_band=_quality_band(page_score),
                d50_focus_query=str(row.get("query") or "").strip() in focus_queries,
                label_source=PAGE_LABEL_SOURCE_V5,
                labeler=labeler,
                notes=(
                    "deterministic_expert_rubric=true; human_label=false; "
                    "page_score_carried_from_dataset_v4=true; ranking_target_used_for_preferences=true"
                ),
            )
        )
    return labels


def _group_rows(rows: Sequence[Mapping[str, str]]) -> dict[str, list[Mapping[str, str]]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("query") or "").strip()].append(row)
    return dict(grouped)


def _strength_for_margin(margin: float, *, strong_margin: float, weak_margin: float, uncertain_margin: float) -> str | None:
    absolute = abs(float(margin))
    if absolute >= strong_margin:
        return "strong"
    if absolute >= weak_margin:
        return "weak"
    if absolute >= uncertain_margin:
        return "uncertain"
    return None


def _weight_for_strength(strength: str, *, d50_recovery: bool = False) -> float:
    if strength == "strong":
        return 1.25 if d50_recovery else 1.0
    if strength == "weak":
        return 0.65 if d50_recovery else 0.5
    return 0.0


def _make_preference(
    *,
    query: str,
    winner: Mapping[str, str],
    loser: Mapping[str, str],
    strength: str,
    reason: str,
    patterns: Sequence[str] = (),
    d50_focus_query: bool,
    d50_recovery: bool = False,
    labeler: str = DEFAULT_LABELER,
) -> PreferenceLabel:
    winner_page_score = _safe_float(winner.get("target_score"))
    loser_page_score = _safe_float(loser.get("target_score"))
    winner_target = _ranking_target_score(winner)
    loser_target = _ranking_target_score(loser)
    winner_rank = _safe_int(winner.get("rank"))
    loser_rank = _safe_int(loser.get("rank"))
    return PreferenceLabel(
        query=query,
        winner_url=str(winner.get("url") or "").strip(),
        loser_url=str(loser.get("url") or "").strip(),
        preference_strength=strength,
        usable_for_training=strength in {"strong", "weak"},
        weight=_weight_for_strength(strength, d50_recovery=d50_recovery),
        winner_page_score=round(winner_page_score, 4),
        loser_page_score=round(loser_page_score, 4),
        winner_ranking_target=winner_target,
        loser_ranking_target=loser_target,
        target_margin=round(winner_target - loser_target, 4),
        winner_rank=winner_rank,
        loser_rank=loser_rank,
        serp_rank_delta=loser_rank - winner_rank,
        label_source=PREFERENCE_LABEL_SOURCE_V5,
        labeler=labeler,
        reason=reason,
        patterns="|".join(sorted(set(patterns))),
        d50_focus_query=d50_focus_query,
    )


def _preference_key(preference: PreferenceLabel) -> tuple[str, str, str]:
    return (preference.query, preference.winner_url, preference.loser_url)


def _better_by_ranking_target(first: Mapping[str, str], second: Mapping[str, str]) -> tuple[Mapping[str, str], Mapping[str, str], float]:
    first_target = _ranking_target_score(first)
    second_target = _ranking_target_score(second)
    if first_target >= second_target:
        return first, second, first_target - second_target
    return second, first, second_target - first_target


def _row_by_url(rows: Sequence[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {str(row.get("url") or "").strip(): row for row in rows if str(row.get("url") or "").strip()}


def _urls_from_diagnostic_items(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item.get("url") or "").strip() for item in items if isinstance(item, dict) and str(item.get("url") or "").strip()]


def _d50_recovery_strength(lost_row: Mapping[str, str], promoted_row: Mapping[str, str]) -> str:
    lost_page_score = _safe_float(lost_row.get("target_score"))
    promoted_page_score = _safe_float(promoted_row.get("target_score"))
    lost_critical = _critical_search_score(lost_row)
    promoted_critical = _critical_search_score(promoted_row)
    # SERP top-3 is evidence, not truth: if the SERP row is clearly worse by
    # page score and critical signals, keep it as review evidence only.
    if lost_page_score + 12.0 < promoted_page_score and lost_critical + 8.0 < promoted_critical:
        return "uncertain"
    if lost_page_score + 3.0 >= promoted_page_score or lost_critical >= promoted_critical:
        return "strong"
    return "weak"


def build_preference_labels(
    rows: Sequence[Mapping[str, str]],
    *,
    d50_report: Mapping[str, Any] | None = None,
    strong_margin: float = 8.0,
    weak_margin: float = 4.0,
    uncertain_margin: float = 2.0,
    labeler: str = DEFAULT_LABELER,
) -> list[PreferenceLabel]:
    d50_payload = d50_report or {}
    focus_queries = _d50_focus_queries(d50_payload)
    diagnostics_by_query = _d50_diagnostics_by_query(d50_payload)
    preferences: dict[tuple[str, str, str], PreferenceLabel] = {}

    for query, query_rows in _group_rows(rows).items():
        sorted_rows = sorted(query_rows, key=lambda row: (_safe_int(row.get("rank"), 9999), str(row.get("url") or "")))
        for index, first in enumerate(sorted_rows):
            for second in sorted_rows[index + 1 :]:
                winner, loser, margin = _better_by_ranking_target(first, second)
                strength = _strength_for_margin(
                    margin,
                    strong_margin=strong_margin,
                    weak_margin=weak_margin,
                    uncertain_margin=uncertain_margin,
                )
                if strength is None:
                    continue
                preference = _make_preference(
                    query=query,
                    winner=winner,
                    loser=loser,
                    strength=strength,
                    reason="ranking_target_margin",
                    d50_focus_query=query in focus_queries,
                    labeler=labeler,
                )
                preferences[_preference_key(preference)] = preference

        rows_by_url = _row_by_url(sorted_rows)
        for diagnostic in diagnostics_by_query.get(query, []):
            patterns = diagnostic.get("patterns") if isinstance(diagnostic.get("patterns"), list) else []
            lost_urls = _urls_from_diagnostic_items(diagnostic.get("lost_actual_top3"))
            promoted_urls = _urls_from_diagnostic_items(diagnostic.get("promoted_non_top3"))
            for lost_url in lost_urls:
                lost_row = rows_by_url.get(lost_url)
                if lost_row is None:
                    continue
                for promoted_url in promoted_urls:
                    promoted_row = rows_by_url.get(promoted_url)
                    if promoted_row is None:
                        continue
                    strength = _d50_recovery_strength(lost_row, promoted_row)
                    if strength == "uncertain":
                        winner, loser, _margin = _better_by_ranking_target(lost_row, promoted_row)
                        reason = "d50_top3_conflict_manual_review"
                    else:
                        winner, loser = lost_row, promoted_row
                        reason = "d50_top3_recovery"
                    preference = _make_preference(
                        query=query,
                        winner=winner,
                        loser=loser,
                        strength=strength,
                        reason=reason,
                        patterns=[str(pattern) for pattern in patterns],
                        d50_focus_query=True,
                        d50_recovery=True,
                        labeler=labeler,
                    )
                    existing = preferences.get(_preference_key(preference))
                    if existing is None or (
                        preference.reason.startswith("d50") and not existing.reason.startswith("d50")
                    ):
                        preferences[_preference_key(preference)] = preference

    return sorted(
        preferences.values(),
        key=lambda preference: (
            preference.query,
            0 if preference.reason.startswith("d50") else 1,
            preference.winner_url,
            preference.loser_url,
        ),
    )


def validate_preference_split(
    preferences: Sequence[PreferenceLabel],
    split: Mapping[str, object],
    *,
    d50_focus_queries: set[str] | None = None,
) -> dict[str, object]:
    train_queries = {str(query).strip() for query in split.get("train_queries") or [] if str(query).strip()}
    validation_queries = {str(query).strip() for query in split.get("validation_queries") or [] if str(query).strip()}
    overlap = sorted(train_queries & validation_queries)
    preference_queries = {preference.query for preference in preferences}
    unknown_queries = sorted(preference_queries - train_queries - validation_queries)
    d50_focus = d50_focus_queries or set()
    d50_represented = {
        preference.query
        for preference in preferences
        if preference.query in d50_focus and preference.usable_for_training
    }
    return {
        "passed": not overlap and not unknown_queries and d50_focus <= preference_queries,
        "split_mode": str(split.get("split_mode") or ""),
        "train_queries_count": len(train_queries),
        "validation_queries_count": len(validation_queries),
        "preference_queries_count": len(preference_queries),
        "query_overlap_count": len(overlap),
        "query_overlap": overlap,
        "unknown_preference_queries_count": len(unknown_queries),
        "unknown_preference_queries": unknown_queries,
        "d50_focus_queries_count": len(d50_focus),
        "d50_focus_queries_represented_count": len(d50_represented),
        "d50_focus_queries_missing_count": len(d50_focus - preference_queries),
        "d50_focus_queries_missing": sorted(d50_focus - preference_queries),
        "train_preferences_count": sum(1 for preference in preferences if preference.query in train_queries),
        "validation_preferences_count": sum(1 for preference in preferences if preference.query in validation_queries),
        "usable_preferences_count": sum(1 for preference in preferences if preference.usable_for_training),
        "uncertain_preferences_count": sum(1 for preference in preferences if preference.preference_strength == "uncertain"),
    }


def _score_distribution(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "mean": 0.0, "max": 0.0}
    sorted_values = sorted(float(value) for value in values)

    def percentile(ratio: float) -> float:
        index = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * ratio)))
        return round(sorted_values[index], 4)

    return {
        "min": round(min(sorted_values), 4),
        "p25": percentile(0.25),
        "mean": round(fmean(sorted_values), 4),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "max": round(max(sorted_values), 4),
    }


def _counter(values: Sequence[str]) -> dict[str, int]:
    counter = Counter(values)
    return {key: counter[key] for key in sorted(counter)}


def _copy_or_update_dataset(
    *,
    source_path: Path,
    output_path: Path,
    dataset_version: str,
    label_schema_version: str,
) -> list[dict[str, object]]:
    fieldnames, rows = _read_csv_rows(source_path)
    if not fieldnames or not rows:
        raise ValueError(f"Source dataset is empty or missing: {source_path}")
    output_rows: list[dict[str, object]] = []
    for row in rows:
        output_row: dict[str, object] = dict(row)
        output_row["dataset_version"] = dataset_version
        output_row["label_schema_version"] = label_schema_version
        output_row["label_source"] = PAGE_LABEL_SOURCE_V5
        output_rows.append(output_row)
    _write_csv_rows(output_path, fieldnames, output_rows)
    return output_rows


def _copy_or_update_auxiliary_csv(source_path: Path, output_path: Path, *, dataset_version: str) -> dict[str, object]:
    fieldnames, rows = _read_csv_rows(source_path)
    if not fieldnames:
        return {"source_path": str(source_path), "output_path": str(output_path), "copied": False, "rows_count": 0}
    updated_rows: list[dict[str, object]] = []
    for row in rows:
        output_row: dict[str, object] = dict(row)
        if "dataset_version" in output_row:
            output_row["dataset_version"] = dataset_version
        updated_rows.append(output_row)
    _write_csv_rows(output_path, fieldnames, updated_rows)
    return {"source_path": str(source_path), "output_path": str(output_path), "copied": True, "rows_count": len(rows)}


def _copy_auxiliary_files(
    *,
    source_failures_path: Path,
    source_seeds_path: Path,
    output_failures_path: Path,
    output_seeds_path: Path,
    dataset_version: str,
) -> dict[str, object]:
    failures = _copy_or_update_auxiliary_csv(source_failures_path, output_failures_path, dataset_version=dataset_version)
    seeds = {"source_path": str(source_seeds_path), "output_path": str(output_seeds_path), "copied": False, "rows_count": 0}
    if source_seeds_path.exists():
        output_seeds_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_seeds_path, output_seeds_path)
        _fields, seed_rows = _read_csv_rows(output_seeds_path)
        seeds = {"source_path": str(source_seeds_path), "output_path": str(output_seeds_path), "copied": True, "rows_count": len(seed_rows)}
    return {"failures": failures, "seeds": seeds}


def _write_page_labels(path: Path, labels: Sequence[PageLabel]) -> None:
    _write_csv_rows(path, PAGE_LABEL_FIELDS, [asdict(label) for label in labels])


def _write_preference_labels(path: Path, preferences: Sequence[PreferenceLabel]) -> None:
    _write_csv_rows(path, PREFERENCE_FIELDS, [asdict(preference) for preference in preferences])


def _build_report(
    *,
    source_dataset_path: Path,
    output_dataset_path: Path,
    page_labels_path: Path,
    preference_labels_path: Path,
    rows: Sequence[Mapping[str, object]],
    page_labels: Sequence[PageLabel],
    preferences: Sequence[PreferenceLabel],
    split: Mapping[str, object],
    split_validation: Mapping[str, object],
    manifest: Mapping[str, object],
    d50_report_path: Path,
    d50_report: Mapping[str, Any],
    auxiliary_files: Mapping[str, object],
    production_artifact_path: Path,
) -> dict[str, object]:
    usable_preferences = [preference for preference in preferences if preference.usable_for_training]
    d50_focus_queries = _d50_focus_queries(d50_report)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D51",
        "dataset_version": DEFAULT_DATASET_VERSION,
        "source_dataset_version": "dataset-v4",
        "source_dataset_path": str(source_dataset_path),
        "output_dataset_path": str(output_dataset_path),
        "page_labels_path": str(page_labels_path),
        "preference_labels_path": str(preference_labels_path),
        "d50_report_path": str(d50_report_path),
        "label_schema_version": LABEL_SCHEMA_VERSION_V5,
        "label_semantics": {
            "deterministic_expert_rubric": True,
            "human_labels": False,
            "serp_rank_is_signal_not_truth": True,
            "uncertain_preferences_have_zero_training_weight": True,
        },
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "page_labels_count": len(page_labels),
        "preference_labels_count": len(preferences),
        "usable_preference_labels_count": len(usable_preferences),
        "preference_strength_distribution": _counter([preference.preference_strength for preference in preferences]),
        "preference_reason_distribution": _counter([preference.reason for preference in preferences]),
        "preference_pattern_distribution": _counter(
            pattern
            for preference in preferences
            for pattern in preference.patterns.split("|")
            if pattern
        ),
        "page_score_distribution": _score_distribution([label.page_target_score for label in page_labels]),
        "ranking_target_distribution": _score_distribution([label.ranking_target_score for label in page_labels]),
        "d50_focus": {
            "queries_count": len(d50_focus_queries),
            "queries": sorted(d50_focus_queries),
            "represented_in_preferences_count": split_validation.get("d50_focus_queries_represented_count"),
            "missing_queries_count": split_validation.get("d50_focus_queries_missing_count"),
        },
        "split": dict(split),
        "split_validation": dict(split_validation),
        "manifest_ready_for_training": bool(manifest.get("quality_gates", {}).get("ready_for_training")),
        "manifest_quality_gates": manifest.get("quality_gates"),
        "manifest_path": manifest.get("manifest_path"),
        "auxiliary_files": dict(auxiliary_files),
        "production_artifact": {
            "path": str(production_artifact_path),
            "sha1": _sha1(production_artifact_path),
            "changed_by_d51": False,
        },
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, report: Mapping[str, object]) -> None:
    split_validation = report.get("split_validation") if isinstance(report.get("split_validation"), dict) else {}
    d50_focus = report.get("d50_focus") if isinstance(report.get("d50_focus"), dict) else {}
    lines = [
        "# D51 Query-Level Preference Labels",
        "",
        f"- Dataset version: `{report.get('dataset_version')}`",
        f"- Source dataset: `{report.get('source_dataset_version')}`",
        f"- Output dataset: `{report.get('output_dataset_path')}`",
        f"- Page labels: `{report.get('page_labels_count')}`",
        f"- Preference labels: `{report.get('preference_labels_count')}`",
        f"- Usable preferences: `{report.get('usable_preference_labels_count')}`",
        f"- Split validation: `{'passed' if split_validation.get('passed') else 'failed'}`",
        f"- Manifest ready for training: `{report.get('manifest_ready_for_training')}`",
        f"- Production artifact changed by D51: `{report.get('production_artifact', {}).get('changed_by_d51') if isinstance(report.get('production_artifact'), dict) else False}`",
        "",
        "## Preference Strengths",
        "",
    ]
    strengths = report.get("preference_strength_distribution") if isinstance(report.get("preference_strength_distribution"), dict) else {}
    lines.extend(f"- `{key}`: `{value}`" for key, value in strengths.items())
    lines.extend(["", "## Preference Reasons", ""])
    reasons = report.get("preference_reason_distribution") if isinstance(report.get("preference_reason_distribution"), dict) else {}
    lines.extend(f"- `{key}`: `{value}`" for key, value in reasons.items())
    lines.extend(
        [
            "",
            "## D50 Focus",
            "",
            f"- Focus queries: `{d50_focus.get('queries_count')}`",
            f"- Represented in usable preferences: `{d50_focus.get('represented_in_preferences_count')}`",
            f"- Missing: `{d50_focus.get('missing_queries_count')}`",
            "",
            "## Split Validation",
            "",
            f"- Train preferences: `{split_validation.get('train_preferences_count')}`",
            f"- Validation preferences: `{split_validation.get('validation_preferences_count')}`",
            f"- Unknown preference queries: `{split_validation.get('unknown_preference_queries_count')}`",
            f"- Query overlap: `{split_validation.get('query_overlap_count')}`",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_v5_query_preference_dataset(
    *,
    source_dataset_path: str | Path = DEFAULT_SOURCE_DATASET_PATH,
    source_failures_path: str | Path = DEFAULT_SOURCE_FAILURES_PATH,
    source_seeds_path: str | Path = DEFAULT_SOURCE_SEEDS_PATH,
    source_artifacts_dir: str | Path = DEFAULT_SOURCE_ARTIFACTS_DIR,
    d50_report_path: str | Path = DEFAULT_D50_REPORT_JSON_PATH,
    output_dataset_path: str | Path = DEFAULT_OUTPUT_DATASET_PATH,
    output_failures_path: str | Path = DEFAULT_OUTPUT_FAILURES_PATH,
    output_seeds_path: str | Path = DEFAULT_OUTPUT_SEEDS_PATH,
    output_split_path: str | Path = DEFAULT_OUTPUT_SPLIT_PATH,
    output_manifest_path: str | Path = DEFAULT_OUTPUT_MANIFEST_PATH,
    output_page_labels_path: str | Path = DEFAULT_OUTPUT_PAGE_LABELS_PATH,
    output_preference_labels_path: str | Path = DEFAULT_OUTPUT_PREFERENCE_LABELS_PATH,
    output_split_validation_path: str | Path = DEFAULT_OUTPUT_SPLIT_VALIDATION_PATH,
    output_report_json_path: str | Path = DEFAULT_OUTPUT_REPORT_JSON_PATH,
    output_report_markdown_path: str | Path = DEFAULT_OUTPUT_REPORT_MD_PATH,
    production_artifact_path: str | Path = DEFAULT_PRODUCTION_ARTIFACT_PATH,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    thresholds: DatasetQualityThresholds = PRODUCTION_LIKE_DATASET_THRESHOLDS,
) -> dict[str, object]:
    resolved_source_dataset_path = Path(source_dataset_path)
    resolved_source_failures_path = Path(source_failures_path)
    resolved_source_seeds_path = Path(source_seeds_path)
    resolved_source_artifacts_dir = Path(source_artifacts_dir)
    resolved_d50_report_path = Path(d50_report_path)
    resolved_output_dataset_path = Path(output_dataset_path)
    resolved_output_failures_path = Path(output_failures_path)
    resolved_output_seeds_path = Path(output_seeds_path)
    resolved_output_split_path = Path(output_split_path)
    resolved_output_manifest_path = Path(output_manifest_path)
    resolved_output_page_labels_path = Path(output_page_labels_path)
    resolved_output_preference_labels_path = Path(output_preference_labels_path)
    resolved_output_split_validation_path = Path(output_split_validation_path)
    resolved_output_report_json_path = Path(output_report_json_path)
    resolved_output_report_markdown_path = Path(output_report_markdown_path)
    resolved_production_artifact_path = Path(production_artifact_path)

    d50_report = json.loads(resolved_d50_report_path.read_text(encoding="utf-8"))
    output_rows = _copy_or_update_dataset(
        source_path=resolved_source_dataset_path,
        output_path=resolved_output_dataset_path,
        dataset_version=dataset_version,
        label_schema_version=LABEL_SCHEMA_VERSION_V5,
    )
    auxiliary_files = _copy_auxiliary_files(
        source_failures_path=resolved_source_failures_path,
        source_seeds_path=resolved_source_seeds_path,
        output_failures_path=resolved_output_failures_path,
        output_seeds_path=resolved_output_seeds_path,
        dataset_version=dataset_version,
    )
    page_labels = build_page_labels(output_rows, d50_focus_queries=_d50_focus_queries(d50_report))
    preferences = build_preference_labels(output_rows, d50_report=d50_report)
    _write_page_labels(resolved_output_page_labels_path, page_labels)
    _write_preference_labels(resolved_output_preference_labels_path, preferences)

    split = create_dataset_split(
        resolved_output_dataset_path,
        resolved_output_split_path,
        dataset_version=dataset_version,
    )
    split_validation = validate_preference_split(
        preferences,
        split,
        d50_focus_queries=_d50_focus_queries(d50_report),
    )
    _write_json(resolved_output_split_validation_path, split_validation)
    manifest = save_dataset_manifest(
        dataset_path=resolved_output_dataset_path,
        failures_path=resolved_output_failures_path if resolved_output_failures_path.exists() else None,
        seeds_path=resolved_output_seeds_path if resolved_output_seeds_path.exists() else None,
        output_path=resolved_output_manifest_path,
        thresholds=thresholds,
        dataset_version=dataset_version,
        baseline_version=BASELINE_DATASET_VERSION,
        artifacts_dir=resolved_source_artifacts_dir,
        split_path=resolved_output_split_path,
    )
    report = _build_report(
        source_dataset_path=resolved_source_dataset_path,
        output_dataset_path=resolved_output_dataset_path,
        page_labels_path=resolved_output_page_labels_path,
        preference_labels_path=resolved_output_preference_labels_path,
        rows=output_rows,
        page_labels=page_labels,
        preferences=preferences,
        split=split,
        split_validation=split_validation,
        manifest=manifest,
        d50_report_path=resolved_d50_report_path,
        d50_report=d50_report,
        auxiliary_files=auxiliary_files,
        production_artifact_path=resolved_production_artifact_path,
    )
    _write_json(resolved_output_report_json_path, report)
    _write_markdown(resolved_output_report_markdown_path, report)
    return {
        **report,
        "report_json_path": str(resolved_output_report_json_path),
        "report_markdown_path": str(resolved_output_report_markdown_path),
        "split_validation_path": str(resolved_output_split_validation_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build D51 query-level preference labels for dataset-v5.")
    parser.add_argument("--source-dataset", default=str(DEFAULT_SOURCE_DATASET_PATH))
    parser.add_argument("--source-failures", default=str(DEFAULT_SOURCE_FAILURES_PATH))
    parser.add_argument("--source-seeds", default=str(DEFAULT_SOURCE_SEEDS_PATH))
    parser.add_argument("--source-artifacts-dir", default=str(DEFAULT_SOURCE_ARTIFACTS_DIR))
    parser.add_argument("--d50-report", default=str(DEFAULT_D50_REPORT_JSON_PATH))
    parser.add_argument("--output-dataset", default=str(DEFAULT_OUTPUT_DATASET_PATH))
    parser.add_argument("--output-failures", default=str(DEFAULT_OUTPUT_FAILURES_PATH))
    parser.add_argument("--output-seeds", default=str(DEFAULT_OUTPUT_SEEDS_PATH))
    parser.add_argument("--output-split", default=str(DEFAULT_OUTPUT_SPLIT_PATH))
    parser.add_argument("--output-manifest", default=str(DEFAULT_OUTPUT_MANIFEST_PATH))
    parser.add_argument("--output-page-labels", default=str(DEFAULT_OUTPUT_PAGE_LABELS_PATH))
    parser.add_argument("--output-preference-labels", default=str(DEFAULT_OUTPUT_PREFERENCE_LABELS_PATH))
    parser.add_argument("--output-split-validation", default=str(DEFAULT_OUTPUT_SPLIT_VALIDATION_PATH))
    parser.add_argument("--output-report-json", default=str(DEFAULT_OUTPUT_REPORT_JSON_PATH))
    parser.add_argument("--output-report-md", default=str(DEFAULT_OUTPUT_REPORT_MD_PATH))
    parser.add_argument("--production-artifact", default=str(DEFAULT_PRODUCTION_ARTIFACT_PATH))
    args = parser.parse_args()
    report = build_v5_query_preference_dataset(
        source_dataset_path=args.source_dataset,
        source_failures_path=args.source_failures,
        source_seeds_path=args.source_seeds,
        source_artifacts_dir=args.source_artifacts_dir,
        d50_report_path=args.d50_report,
        output_dataset_path=args.output_dataset,
        output_failures_path=args.output_failures,
        output_seeds_path=args.output_seeds,
        output_split_path=args.output_split,
        output_manifest_path=args.output_manifest,
        output_page_labels_path=args.output_page_labels,
        output_preference_labels_path=args.output_preference_labels,
        output_split_validation_path=args.output_split_validation,
        output_report_json_path=args.output_report_json,
        output_report_markdown_path=args.output_report_md,
        production_artifact_path=args.production_artifact,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
