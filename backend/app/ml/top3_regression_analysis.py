from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact
from app.ml.publish import ARTIFACTS_DIR
from app.ml.seo_weighted_candidate_training import DEFAULT_D47_DATASET_PATH
from app.ml.seo_weighted_shadow_benchmark import DEFAULT_D48_REPORT_JSON_PATH
from app.ml.train import load_dataset_rows, rows_to_matrix, split_dataset_rows


DEFAULT_D50_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v5-d50"
DEFAULT_D50_REPORT_JSON_PATH = DEFAULT_D50_OUTPUT_DIR / "top3-regression-analysis.json"
DEFAULT_D50_REPORT_MD_PATH = DEFAULT_D50_OUTPUT_DIR / "top3-regression-analysis.md"

REFERENCE_MODEL_NAME = "production_catboost_v3"
KNOWN_AGGREGATOR_HINTS = (
    "avito",
    "market",
    "ozon",
    "wildberries",
    "yandex",
    "2gis",
    "zoon",
    "flamp",
    "otzovik",
    "irecommend",
    "profi",
    "youdo",
    "tiu",
    "pulscen",
    "blizko",
    "dzen",
)
TEXT_VOLUME_FEATURES = ("word_count", "text_length_chars", "paragraph_count", "sentence_count")
SEMANTIC_FEATURES = (
    "semantic_similarity",
    "query_semantic_alignment",
    "keyword_coverage_ratio",
    "intent_alignment_score",
    "commercial_intent_alignment",
    "local_intent_alignment",
    "informational_intent_alignment",
)
TECHNICAL_FEATURES = (
    "http_status_ok",
    "canonical_signal_score",
    "page_indexable",
    "technical_seo_score",
    "technical_metadata_score",
)
COMMERCIAL_FEATURES = (
    "commercial_signal_score",
    "trust_signal_score",
    "price_present",
    "phone_present",
    "business_identity_score",
    "contact_signal_score",
)


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


def _sha1_file(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved_path = Path(path)
    if not resolved_path.exists() or not resolved_path.is_file():
        return None
    digest = hashlib.sha1()
    with resolved_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path.split("/")[0]
    return host.casefold().removeprefix("www.")


def _is_aggregator(row: Mapping[str, Any]) -> bool:
    haystack = f"{row.get('url', '')} {row.get('domain', '')} {row.get('title', '')}".casefold()
    return any(hint in haystack for hint in KNOWN_AGGREGATOR_HINTS)


def _feature_average(row: Mapping[str, Any], feature_names: Sequence[str]) -> float:
    values = [_safe_float(row.get(feature_name)) for feature_name in feature_names if feature_name in row]
    return sum(values) / len(values) if values else 0.0


def _summarize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    url = str(row.get("url") or "")
    return {
        "url": url,
        "domain": str(row.get("domain") or _domain_from_url(url)),
        "rank": _safe_int(row.get("rank")),
        "target_score": round(_safe_float(row.get("target_score")), 4),
        "intent": str(row.get("intent") or "unknown"),
        "label_source": str(row.get("label_source") or ""),
        "fetch_status": str(row.get("fetch_status") or "ok"),
        "word_count": round(_safe_float(row.get("word_count")), 4),
        "semantic_similarity": round(_safe_float(row.get("semantic_similarity")), 4),
        "keyword_coverage_ratio": round(_safe_float(row.get("keyword_coverage_ratio")), 4),
        "intent_alignment_score": round(_safe_float(row.get("intent_alignment_score")), 4),
        "technical_seo_score": round(_safe_float(row.get("technical_seo_score")), 4),
        "commercial_signal_score": round(_safe_float(row.get("commercial_signal_score")), 4),
        "is_aggregator_like": _is_aggregator(row),
    }


def _rank_entries(
    rows: Sequence[Mapping[str, Any]],
    predictions: Sequence[float],
    *,
    rank_field: str,
) -> dict[str, dict[str, Any]]:
    ranked_pairs = sorted(
        zip(rows, predictions, strict=False),
        key=lambda pair: (float(pair[1]), -_safe_int(pair[0].get("rank")), str(pair[0].get("url") or "")),
        reverse=True,
    )
    entries: dict[str, dict[str, Any]] = {}
    for predicted_rank, (row, prediction) in enumerate(ranked_pairs, start=1):
        url = str(row.get("url") or "")
        entries[url] = {
            **_summarize_row(row),
            rank_field: predicted_rank,
            f"{rank_field}_score": round(float(prediction), 4),
        }
    return entries


def _merge_model_entries(
    rows: Sequence[Mapping[str, Any]],
    predictions_by_model: Mapping[str, Sequence[float]],
) -> dict[str, dict[str, Any]]:
    merged = {str(row.get("url") or ""): _summarize_row(row) for row in rows}
    for model_name, predictions in predictions_by_model.items():
        ranked = _rank_entries(rows, predictions, rank_field=f"{model_name}_predicted_rank")
        for url, model_entry in ranked.items():
            merged.setdefault(url, {}).update(
                {
                    f"{model_name}_predicted_rank": model_entry[f"{model_name}_predicted_rank"],
                    f"{model_name}_predicted_rank_score": model_entry[f"{model_name}_predicted_rank_score"],
                }
            )
    return merged


def _model_top_urls(
    rows: Sequence[Mapping[str, Any]],
    predictions: Sequence[float],
    *,
    limit: int = 3,
) -> set[str]:
    ranked_pairs = sorted(
        zip(rows, predictions, strict=False),
        key=lambda pair: (float(pair[1]), -_safe_int(pair[0].get("rank")), str(pair[0].get("url") or "")),
        reverse=True,
    )
    return {str(row.get("url") or "") for row, _prediction in ranked_pairs[:limit]}


def _actual_top_urls(rows: Sequence[Mapping[str, Any]], *, limit: int = 3) -> set[str]:
    ranked_rows = sorted(rows, key=lambda row: (_safe_int(row.get("rank"), 9999), str(row.get("url") or "")))
    return {str(row.get("url") or "") for row in ranked_rows[:limit]}


def _dominant_delta(
    promoted_rows: Sequence[Mapping[str, Any]],
    lost_rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
) -> float:
    if not promoted_rows or not lost_rows:
        return 0.0
    promoted = sum(_feature_average(row, feature_names) for row in promoted_rows) / len(promoted_rows)
    lost = sum(_feature_average(row, feature_names) for row in lost_rows) / len(lost_rows)
    return promoted - lost


def classify_failure_patterns(
    *,
    lost_rows: Sequence[Mapping[str, Any]],
    promoted_rows: Sequence[Mapping[str, Any]],
    candidate_top_feature: str | None = None,
    candidate_top_feature_group: str | None = None,
) -> list[str]:
    patterns: list[str] = []
    top_feature = (candidate_top_feature or "").casefold()
    top_group = (candidate_top_feature_group or "").casefold()
    text_delta = _dominant_delta(promoted_rows, lost_rows, TEXT_VOLUME_FEATURES)
    semantic_delta = _dominant_delta(promoted_rows, lost_rows, SEMANTIC_FEATURES)
    technical_delta = _dominant_delta(promoted_rows, lost_rows, TECHNICAL_FEATURES)
    commercial_delta = _dominant_delta(promoted_rows, lost_rows, COMMERCIAL_FEATURES)
    rank_delta = _dominant_delta(promoted_rows, lost_rows, ("rank",))

    if text_delta > 250 or "word_count" in top_feature or top_group == "supporting":
        patterns.append("shortcut_text_volume")
    if semantic_delta < -0.05:
        patterns.append("semantic_or_intent_mismatch")
    if technical_delta < -0.05:
        patterns.append("technical_indexability_mismatch")
    if commercial_delta > 0.08 and semantic_delta <= 0.02:
        patterns.append("weak_commercial_signal_overweighted")
    if rank_delta > 2.0:
        patterns.append("rank_prior_disagreement")
    if any(_is_aggregator(row) for row in [*lost_rows, *promoted_rows]):
        patterns.append("aggregator_or_marketplace_distortion")
    if not patterns:
        patterns.append("unknown_requires_manual_review")
    return sorted(set(patterns))


def _candidate_feature_guardrail(d48_report: Mapping[str, Any], candidate_name: str) -> dict[str, Any]:
    product_guardrails = d48_report.get("product_guardrails")
    if not isinstance(product_guardrails, dict):
        return {}
    guardrail = product_guardrails.get(candidate_name)
    if not isinstance(guardrail, dict):
        return {}
    feature_guardrail = guardrail.get("feature_importance_guardrail")
    return feature_guardrail if isinstance(feature_guardrail, dict) else {}


def _query_groups(rows: Sequence[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("query") or "")].append(row)
    return dict(grouped)


def _query_group_indices(rows: Sequence[dict[str, str]]) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[str(row.get("query") or "")].append(index)
    return dict(grouped)


def build_top3_regression_report_from_predictions(
    *,
    validation_rows: Sequence[dict[str, str]],
    predictions_by_model: Mapping[str, Sequence[float]],
    reference_model_name: str,
    candidate_model_names: Sequence[str],
    d48_report: Mapping[str, Any] | None = None,
    production_sha1: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    d48_payload = d48_report or {}
    grouped_indices = _query_group_indices(validation_rows)
    candidate_summaries: dict[str, dict[str, Any]] = {}
    query_diagnostics: list[dict[str, Any]] = []
    pattern_counts: Counter[str] = Counter()
    total_regressions = 0
    d51_focus_queries: set[str] = set()

    for candidate_name in candidate_model_names:
        candidate_summaries[candidate_name] = {
            "queries_count": len(grouped_indices),
            "regressed_queries_count": 0,
            "improved_queries_count": 0,
            "same_hit_queries_count": 0,
            "reference_hit_candidate_missed_count": 0,
            "candidate_hit_reference_missed_count": 0,
            "patterns": {},
            "examples": [],
        }

    for query, query_indices in sorted(grouped_indices.items()):
        query_rows = [validation_rows[index] for index in query_indices]
        actual_top = _actual_top_urls(query_rows)
        reference_predictions = predictions_by_model[reference_model_name]
        reference_query_predictions = [reference_predictions[index] for index in query_indices]
        reference_top = _model_top_urls(query_rows, reference_query_predictions)
        reference_hit = bool(reference_top & actual_top)
        query_predictions_by_model = {
            model_name: [predictions[index] for index in query_indices]
            for model_name, predictions in predictions_by_model.items()
        }
        merged_entries = _merge_model_entries(query_rows, query_predictions_by_model)

        for candidate_name in candidate_model_names:
            candidate_predictions = query_predictions_by_model[candidate_name]
            candidate_top = _model_top_urls(query_rows, candidate_predictions)
            candidate_hit = bool(candidate_top & actual_top)
            summary = candidate_summaries[candidate_name]
            if reference_hit and not candidate_hit:
                summary["regressed_queries_count"] += 1
                summary["reference_hit_candidate_missed_count"] += 1
                total_regressions += 1
                d51_focus_queries.add(query)
                lost_urls = actual_top - candidate_top
                promoted_urls = candidate_top - actual_top
                lost_rows = [row for row in query_rows if str(row.get("url") or "") in lost_urls]
                promoted_rows = [row for row in query_rows if str(row.get("url") or "") in promoted_urls]
                feature_guardrail = _candidate_feature_guardrail(d48_payload, candidate_name)
                patterns = classify_failure_patterns(
                    lost_rows=lost_rows,
                    promoted_rows=promoted_rows,
                    candidate_top_feature=str(feature_guardrail.get("top_feature") or ""),
                    candidate_top_feature_group=str(feature_guardrail.get("top_feature_group") or ""),
                )
                for pattern in patterns:
                    pattern_counts[pattern] += 1
                    summary_patterns = summary["patterns"]
                    summary_patterns[pattern] = int(summary_patterns.get(pattern, 0)) + 1
                diagnostic = {
                    "candidate_name": candidate_name,
                    "query": query,
                    "rows_count": len(query_rows),
                    "reference_top3_hit": reference_hit,
                    "candidate_top3_hit": candidate_hit,
                    "actual_serp_top3": [merged_entries[url] for url in actual_top if url in merged_entries],
                    "reference_predicted_top3": [merged_entries[url] for url in reference_top if url in merged_entries],
                    "candidate_predicted_top3": [merged_entries[url] for url in candidate_top if url in merged_entries],
                    "lost_actual_top3": [merged_entries[url] for url in lost_urls if url in merged_entries],
                    "promoted_non_top3": [merged_entries[url] for url in promoted_urls if url in merged_entries],
                    "patterns": patterns,
                    "candidate_top_feature": feature_guardrail.get("top_feature"),
                    "candidate_top_feature_group": feature_guardrail.get("top_feature_group"),
                }
                query_diagnostics.append(diagnostic)
                if len(summary["examples"]) < 5:
                    summary["examples"].append(diagnostic)
            elif candidate_hit and not reference_hit:
                summary["improved_queries_count"] += 1
                summary["candidate_hit_reference_missed_count"] += 1
            else:
                summary["same_hit_queries_count"] += 1

    suggested_focus = [
        {
            "area": "query_level_preference_labels",
            "reason": "Add pairwise/listwise labels for queries where candidate top-3 missed all SERP top-3 pages.",
            "queries": sorted(d51_focus_queries)[:20],
            "queries_count": len(d51_focus_queries),
        },
        {
            "area": "shortcut_feature_control",
            "reason": "Constrain text volume and other supporting signals when they displace stronger SERP pages.",
            "patterns": {
                key: pattern_counts[key]
                for key in ("shortcut_text_volume", "weak_commercial_signal_overweighted")
                if key in pattern_counts
            },
        },
        {
            "area": "serp_relative_manual_review",
            "reason": "Review rank-prior disagreements and aggregator/marketplace distortions before v5 labeling.",
            "patterns": {
                key: pattern_counts[key]
                for key in ("rank_prior_disagreement", "aggregator_or_marketplace_distortion")
                if key in pattern_counts
            },
        },
    ]
    return {
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "task": "D50",
        "decision": "analysis_only",
        "production_artifact": {
            "sha1": production_sha1,
            "unchanged_by_d50": True,
        },
        "inputs": {
            "validation_rows_count": len(validation_rows),
            "validation_queries_count": len(grouped_indices),
            "reference_model_name": reference_model_name,
            "candidate_model_names": list(candidate_model_names),
        },
        "summary": {
            "total_candidate_query_regressions": total_regressions,
            "queries_requiring_d51_focus_count": len(d51_focus_queries),
            "pattern_counts": dict(pattern_counts),
        },
        "candidate_summaries": candidate_summaries,
        "query_diagnostics": query_diagnostics,
        "suggested_d51_focus": suggested_focus,
        "invariants": {
            "validation_only": True,
            "query_group_comparison_only": True,
            "no_training": True,
            "no_publish": True,
        },
    }


def _predict_model(model_path: str | Path, rows: Sequence[dict[str, str]]) -> tuple[str, list[float], dict[str, Any]]:
    artifact = load_model_artifact(model_path)
    if artifact is None:
        raise ValueError(f"Model artifact is unavailable: {model_path}")
    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), (list, tuple)) else None
    matrix, _target = rows_to_matrix(list(rows), feature_columns=feature_columns)
    predictions = [float(value) for value in artifact["model"].predict(matrix)]
    model_info = {
        "model_path": str(Path(model_path)),
        "model_sha1": _sha1_file(model_path),
        "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
        "dataset_version": artifact.get("dataset_version"),
        "model_schema_version": artifact.get("model_schema_version"),
        "artifact_version": artifact.get("artifact_version"),
        "feature_count": len(feature_columns or []),
    }
    return str(model_info["model_path"]), predictions, model_info


def _candidate_name_from_d48(candidate: Mapping[str, Any], fallback_path: str) -> str:
    candidate_name = candidate.get("candidate_name")
    if isinstance(candidate_name, str) and candidate_name.strip():
        return candidate_name.strip()
    return Path(fallback_path).stem


def render_top3_regression_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    production = report.get("production_artifact") if isinstance(report.get("production_artifact"), dict) else {}
    lines = [
        "# D50 Top-3 Regression Analysis",
        "",
        f"- Decision: `{report.get('decision')}`",
        f"- Production SHA1: `{production.get('sha1')}`",
        f"- Production unchanged by D50: `{production.get('unchanged_by_d50')}`",
        f"- Validation queries: `{report.get('inputs', {}).get('validation_queries_count')}`",
        f"- Total candidate/query regressions: `{summary.get('total_candidate_query_regressions')}`",
        f"- Queries for D51 focus: `{summary.get('queries_requiring_d51_focus_count')}`",
        "",
        "## Pattern Summary",
        "",
    ]
    pattern_counts = summary.get("pattern_counts") if isinstance(summary.get("pattern_counts"), dict) else {}
    if pattern_counts:
        for pattern, count in sorted(pattern_counts.items(), key=lambda item: (-int(item[1]), str(item[0]))):
            lines.append(f"- `{pattern}`: `{count}`")
    else:
        lines.append("- No top-3 regressions found.")
    lines.extend(["", "## Candidate Summaries", ""])
    candidate_summaries = report.get("candidate_summaries") if isinstance(report.get("candidate_summaries"), dict) else {}
    for candidate_name, candidate_summary in candidate_summaries.items():
        if not isinstance(candidate_summary, dict):
            continue
        lines.extend(
            [
                f"### {candidate_name}",
                f"- Regressed queries: `{candidate_summary.get('regressed_queries_count')}`",
                f"- Improved queries: `{candidate_summary.get('improved_queries_count')}`",
                f"- Same hit state queries: `{candidate_summary.get('same_hit_queries_count')}`",
                f"- Patterns: `{json.dumps(candidate_summary.get('patterns') or {}, ensure_ascii=False, sort_keys=True)}`",
                "",
            ]
        )
    diagnostics = report.get("query_diagnostics") if isinstance(report.get("query_diagnostics"), list) else []
    lines.extend(["## Regression Examples", ""])
    for diagnostic in diagnostics[:12]:
        if not isinstance(diagnostic, dict):
            continue
        lost = diagnostic.get("lost_actual_top3") if isinstance(diagnostic.get("lost_actual_top3"), list) else []
        promoted = diagnostic.get("promoted_non_top3") if isinstance(diagnostic.get("promoted_non_top3"), list) else []
        lost_domains = ", ".join(str(item.get("domain")) for item in lost if isinstance(item, dict)) or "none"
        promoted_domains = ", ".join(str(item.get("domain")) for item in promoted if isinstance(item, dict)) or "none"
        lines.extend(
            [
                f"### {diagnostic.get('candidate_name')} / {diagnostic.get('query')}",
                f"- Patterns: `{', '.join(diagnostic.get('patterns') or [])}`",
                f"- Lost SERP top-3 domains: `{lost_domains}`",
                f"- Promoted non-top-3 domains: `{promoted_domains}`",
                "",
            ]
        )
    lines.extend(["## D51 Focus", ""])
    for focus in report.get("suggested_d51_focus", []):
        if not isinstance(focus, dict):
            continue
        lines.append(f"- `{focus.get('area')}`: {focus.get('reason')}")
    return "\n".join(lines).strip() + "\n"


def write_top3_regression_report(
    report: Mapping[str, Any],
    *,
    json_path: str | Path = DEFAULT_D50_REPORT_JSON_PATH,
    markdown_path: str | Path = DEFAULT_D50_REPORT_MD_PATH,
) -> dict[str, str]:
    resolved_json_path = Path(json_path)
    resolved_markdown_path = Path(markdown_path)
    resolved_json_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    paths = {"json_path": str(resolved_json_path), "markdown_path": str(resolved_markdown_path)}
    report_with_paths = {**dict(report), "report_paths": paths}
    resolved_json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    resolved_markdown_path.write_text(render_top3_regression_markdown(report_with_paths), encoding="utf-8")
    return paths


def run_d50_top3_regression_analysis(
    *,
    d48_report_path: str | Path = DEFAULT_D48_REPORT_JSON_PATH,
    dataset_path: str | Path | None = None,
    reference_model_path: str | Path = DEFAULT_MODEL_PATH,
    report_json_path: str | Path = DEFAULT_D50_REPORT_JSON_PATH,
    report_markdown_path: str | Path = DEFAULT_D50_REPORT_MD_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    d48_report = json.loads(Path(d48_report_path).read_text(encoding="utf-8"))
    resolved_dataset_path = Path(dataset_path or d48_report.get("dataset_path") or DEFAULT_D47_DATASET_PATH)
    rows = load_dataset_rows(resolved_dataset_path)
    _train_rows, validation_rows, split = split_dataset_rows(rows, test_size=test_size, random_state=random_state)
    if str(split.get("split_mode")) != "group_by_query":
        raise ValueError("D50 requires group_by_query validation split.")
    production_sha1_before = _sha1_file(reference_model_path)
    _reference_path, reference_predictions, reference_info = _predict_model(reference_model_path, validation_rows)
    predictions_by_model = {REFERENCE_MODEL_NAME: reference_predictions}
    candidate_model_names: list[str] = []
    candidate_model_info: dict[str, Any] = {}
    candidates = d48_report.get("shadow_benchmark", {}).get("candidates") if isinstance(d48_report.get("shadow_benchmark"), dict) else []
    for candidate in candidates if isinstance(candidates, list) else []:
        if not isinstance(candidate, dict) or candidate.get("status") != "available":
            continue
        model_path = str(candidate.get("model_path") or "")
        candidate_name = _candidate_name_from_d48(candidate, model_path)
        _path, predictions, model_info = _predict_model(model_path, validation_rows)
        predictions_by_model[candidate_name] = predictions
        candidate_model_names.append(candidate_name)
        candidate_model_info[candidate_name] = model_info

    report = build_top3_regression_report_from_predictions(
        validation_rows=validation_rows,
        predictions_by_model=predictions_by_model,
        reference_model_name=REFERENCE_MODEL_NAME,
        candidate_model_names=candidate_model_names,
        d48_report=d48_report,
        production_sha1=production_sha1_before,
    )
    report["inputs"].update(
        {
            "d48_report_path": str(Path(d48_report_path)),
            "dataset_path": str(resolved_dataset_path),
            "split": {
                **split,
                "test_size": test_size,
                "random_state": random_state,
            },
            "reference_model": reference_info,
            "candidate_models": candidate_model_info,
        }
    )
    production_sha1_after = _sha1_file(reference_model_path)
    report["production_artifact"]["sha1_after"] = production_sha1_after
    report["production_artifact"]["unchanged_by_d50"] = production_sha1_before == production_sha1_after
    if production_sha1_before != production_sha1_after:
        raise RuntimeError(f"Production artifact changed during D50: {production_sha1_before} -> {production_sha1_after}")
    report_paths = write_top3_regression_report(
        report,
        json_path=report_json_path,
        markdown_path=report_markdown_path,
    )
    return {**report, "report_paths": report_paths}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D50 top-3 regression analysis for dataset-v4 candidates.")
    parser.add_argument("--d48-report", default=str(DEFAULT_D48_REPORT_JSON_PATH))
    parser.add_argument("--dataset", default="")
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--report-json", default=str(DEFAULT_D50_REPORT_JSON_PATH))
    parser.add_argument("--report-md", default=str(DEFAULT_D50_REPORT_MD_PATH))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    report = run_d50_top3_regression_analysis(
        d48_report_path=args.d48_report,
        dataset_path=args.dataset or None,
        reference_model_path=args.reference_model,
        report_json_path=args.report_json,
        report_markdown_path=args.report_md,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
