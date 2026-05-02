from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from app.ml.model import DEFAULT_MODEL_PATH, predict_score
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema
from app.ml.shadow_benchmark import run_shadow_benchmark
from app.ml.train import candidate_sort_key, load_dataset_rows, split_dataset_rows
from app.ml.seo_weighted_candidate_training import (
    DEFAULT_D47_CATBOOST_CANDIDATE_PATH,
    DEFAULT_D47_RANKING_CANDIDATE_PATH,
    DEFAULT_D47_RF_CANDIDATE_PATH,
    DEFAULT_D47_DATASET_PATH,
)
from app.ml.publish import ARTIFACTS_DIR


DEFAULT_D48_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v4-d48"
DEFAULT_D48_REPORT_JSON_PATH = DEFAULT_D48_OUTPUT_DIR / "d48-product-critical-shadow-report.json"
DEFAULT_D48_REPORT_MD_PATH = DEFAULT_D48_OUTPUT_DIR / "d48-product-critical-shadow-report.md"
DEFAULT_D48_CANDIDATE_PATHS = (
    DEFAULT_D47_RF_CANDIDATE_PATH,
    DEFAULT_D47_CATBOOST_CANDIDATE_PATH,
    DEFAULT_D47_RANKING_CANDIDATE_PATH,
)
DEFAULT_D48_SMOKE_QUERIES = (
    "ремонт квартир Екатеринбург",
    "пластиковые окна Самара",
    "кухни на заказ Екатеринбург",
    "натяжные потолки Москва",
)

CRITICAL_FEATURE_KEYWORDS = (
    "index",
    "canonical",
    "robots",
    "http_status",
    "technical_seo",
    "title",
    "h1",
    "heading",
    "query",
    "keyword",
    "semantic",
    "intent",
    "viewport",
    "structured_data",
)
SUPPORTING_FEATURE_KEYWORDS = (
    "word_count",
    "text_length",
    "html_length",
    "avg_word",
    "sentence_count",
    "paragraph_count",
    "unique_word",
    "image_count",
    "link_count",
    "list_item",
    "strong_tag",
    "density",
    "price",
    "messenger",
    "payment",
    "delivery",
    "warranty",
    "returns",
    "reviews",
    "rating",
)
CRITICAL_DEGRADATION_FEATURES = {
    "http_status_ok": 0.0,
    "canonical_present": 0.0,
    "canonical_matches_final_url": 0.0,
    "canonical_signal_score": 0.0,
    "page_indexable": 0.0,
    "technical_metadata_score": 0.0,
    "technical_seo_score": 0.0,
    "title_present": 0.0,
    "query_in_title": 0.0,
    "title_keyword_coverage_ratio": 0.0,
    "query_terms_in_headings": 0.0,
    "heading_query_coverage_ratio": 0.0,
    "semantic_similarity": 0.0,
    "query_semantic_alignment": 0.0,
    "title_semantic_alignment": 0.0,
    "heading_semantic_alignment": 0.0,
    "title_heading_keyword_alignment": 0.0,
    "keyword_coverage_ratio": 0.0,
    "query_prominence_score": 0.0,
    "intent_alignment_score": 0.0,
    "commercial_intent_alignment": 0.0,
    "local_intent_alignment": 0.0,
    "informational_intent_alignment": 0.0,
    "navigational_intent_alignment": 0.0,
}
SUPPORTING_DEGRADATION_FEATURES = {
    "text_length_chars": 0.0,
    "html_length_chars": 0.0,
    "word_count": 0.0,
    "unique_word_count": 0.0,
    "sentence_count": 0.0,
    "paragraph_count": 0.0,
    "image_count": 0.0,
    "link_count": 0.0,
    "list_item_count": 0.0,
    "strong_tag_count": 0.0,
    "price_present": 0.0,
    "currency_present": 0.0,
    "delivery_info_present": 0.0,
    "payment_info_present": 0.0,
    "warranty_info_present": 0.0,
    "returns_info_present": 0.0,
    "reviews_present": 0.0,
    "rating_present": 0.0,
    "messenger_present": 0.0,
}


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
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


def _model_name(entry: Mapping[str, Any]) -> str:
    return str(entry.get("candidate_name") or Path(str(entry.get("model_path") or "model")).stem)


def _feature_group(feature_name: str) -> str:
    normalized = feature_name.casefold()
    if any(keyword in normalized for keyword in CRITICAL_FEATURE_KEYWORDS):
        return "critical"
    if any(keyword in normalized for keyword in SUPPORTING_FEATURE_KEYWORDS):
        return "supporting"
    return "important"


def _feature_importance_guardrail(candidate: Mapping[str, Any]) -> dict[str, Any]:
    feature_importance = candidate.get("feature_importance_summary")
    top_features = feature_importance.get("top_features") if isinstance(feature_importance, dict) else []
    rows = [feature for feature in top_features if isinstance(feature, dict)]
    grouped_importance = {"critical": 0.0, "important": 0.0, "supporting": 0.0}
    for feature in rows[:10]:
        feature_name = str(feature.get("feature") or "")
        grouped_importance[_feature_group(feature_name)] += _safe_float(feature.get("importance"))
    top_feature = str(rows[0].get("feature") or "") if rows else ""
    top_feature_group = _feature_group(top_feature) if top_feature else "missing"
    checks = {
        "top_features_present": bool(rows),
        "top_feature_is_not_supporting": top_feature_group != "supporting",
        "critical_importance_at_least_supporting": grouped_importance["critical"] >= grouped_importance["supporting"],
        "critical_signal_in_top_5": any(_feature_group(str(feature.get("feature") or "")) == "critical" for feature in rows[:5]),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "failed_checks": failed,
        "top_feature": top_feature,
        "top_feature_group": top_feature_group,
        "top_10_grouped_importance": {key: round(value, 6) for key, value in grouped_importance.items()},
        "checks": checks,
    }


def _row_to_features(row: Mapping[str, str]) -> dict[str, float]:
    feature_columns = get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns
    return {feature_name: _safe_float(row.get(feature_name)) for feature_name in feature_columns}


def _apply_degradation(features: Mapping[str, float], degradation: Mapping[str, float]) -> dict[str, float]:
    output = dict(features)
    for feature_name, value in degradation.items():
        if feature_name in output:
            output[feature_name] = float(value)
    return output


def _representative_rows(rows: Sequence[dict[str, str]], limit: int = 12) -> list[dict[str, str]]:
    successful_rows = [row for row in rows if str(row.get("fetch_status") or "ok") != "failed"]
    return sorted(successful_rows, key=lambda row: _safe_float(row.get("target_score")), reverse=True)[:limit]


def _score_response_guardrail(
    *,
    model_name: str,
    model_path: str | Path,
    rows: Sequence[dict[str, str]],
) -> dict[str, Any]:
    base_scores: list[float] = []
    critical_drops: list[float] = []
    supporting_drops: list[float] = []
    examples: list[dict[str, Any]] = []
    for row in _representative_rows(rows):
        features = _row_to_features(row)
        base_score = predict_score(features, model_path=model_path)
        critical_score = predict_score(
            _apply_degradation(features, CRITICAL_DEGRADATION_FEATURES),
            model_path=model_path,
        )
        supporting_score = predict_score(
            _apply_degradation(features, SUPPORTING_DEGRADATION_FEATURES),
            model_path=model_path,
        )
        critical_drop = max(0.0, float(base_score) - float(critical_score))
        supporting_drop = max(0.0, float(base_score) - float(supporting_score))
        base_scores.append(float(base_score))
        critical_drops.append(critical_drop)
        supporting_drops.append(supporting_drop)
        if len(examples) < 5:
            examples.append(
                {
                    "query": str(row.get("query") or ""),
                    "url": str(row.get("url") or ""),
                    "base_score": round(float(base_score), 4),
                    "critical_degraded_score": round(float(critical_score), 4),
                    "supporting_degraded_score": round(float(supporting_score), 4),
                    "critical_drop": round(critical_drop, 4),
                    "supporting_drop": round(supporting_drop, 4),
                }
            )

    avg_critical_drop = mean(critical_drops) if critical_drops else 0.0
    avg_supporting_drop = mean(supporting_drops) if supporting_drops else 0.0
    checks = {
        "scores_bounded": all(0.0 <= score <= 100.0 for score in base_scores),
        "critical_drop_positive": avg_critical_drop > 0.5,
        "critical_drop_greater_than_supporting": avg_critical_drop >= avg_supporting_drop + 0.5,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "model_name": model_name,
        "model_path": str(Path(model_path)),
        "passed": not failed,
        "failed_checks": failed,
        "rows_count": len(base_scores),
        "average_base_score": round(mean(base_scores), 4) if base_scores else 0.0,
        "average_critical_drop": round(avg_critical_drop, 4),
        "average_supporting_drop": round(avg_supporting_drop, 4),
        "checks": checks,
        "examples": examples,
    }


def _candidate_by_name(shadow_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = shadow_report.get("candidates") if isinstance(shadow_report.get("candidates"), list) else []
    return {
        _model_name(candidate): candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("status") == "available"
    }


def build_product_guardrails(
    *,
    shadow_report: Mapping[str, Any],
    validation_rows: Sequence[dict[str, str]],
) -> dict[str, Any]:
    candidate_map = _candidate_by_name(shadow_report)
    guardrails: dict[str, Any] = {}
    for candidate_name, candidate in candidate_map.items():
        model_path = str(candidate.get("model_path") or "")
        comparison = next(
            (
                item
                for item in shadow_report.get("candidate_comparisons", [])
                if isinstance(item, dict) and str(item.get("candidate_name")) == candidate_name
            ),
            {},
        )
        base_guardrails = comparison.get("guardrails") if isinstance(comparison.get("guardrails"), dict) else {}
        feature_importance = _feature_importance_guardrail(candidate)
        score_response = _score_response_guardrail(
            model_name=candidate_name,
            model_path=model_path,
            rows=validation_rows,
        )
        checks = {
            "base_shadow_publish_gate_passed": bool(base_guardrails.get("publish_gate_passed")),
            "feature_importance_seo_weighted": bool(feature_importance.get("passed")),
            "critical_failures_penalized_more_than_supporting": bool(score_response.get("passed")),
        }
        failed = [name for name, passed in checks.items() if not passed]
        guardrails[candidate_name] = {
            "passed": not failed,
            "failed_checks": failed,
            "checks": checks,
            "base_rejection_reasons": base_guardrails.get("rejection_reasons") or [],
            "feature_importance_guardrail": feature_importance,
            "score_response_guardrail": score_response,
        }
    return guardrails


def build_d48_decision(
    *,
    shadow_report: Mapping[str, Any],
    product_guardrails: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = _candidate_by_name(shadow_report)
    if not candidates:
        return {
            "publish_recommendation": "needs_more_data",
            "selected_candidate": None,
            "reason": "no_available_candidates",
        }
    eligible_names = [
        candidate_name
        for candidate_name, guardrail in product_guardrails.items()
        if isinstance(guardrail, dict) and guardrail.get("passed") is True
    ]
    if not eligible_names:
        return {
            "publish_recommendation": "keep_current",
            "selected_candidate": None,
            "reason": "no_candidate_passed_product_critical_guardrails",
        }
    reference_model = shadow_report.get("reference_model") if isinstance(shadow_report.get("reference_model"), dict) else {}
    eligible_candidates = [candidates[name] for name in eligible_names]
    selected = max(eligible_candidates, key=candidate_sort_key)
    if candidate_sort_key(selected) <= candidate_sort_key(reference_model):
        return {
            "publish_recommendation": "keep_current",
            "selected_candidate": _model_name(selected),
            "reason": "best_product_gate_passing_candidate_does_not_outperform_current",
        }
    return {
        "publish_recommendation": "publish_candidate",
        "selected_candidate": _model_name(selected),
        "reason": "candidate_passed_shadow_and_product_critical_guardrails",
    }


def _render_markdown(report: Mapping[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    shadow = report.get("shadow_benchmark") if isinstance(report.get("shadow_benchmark"), dict) else {}
    reference_metrics = (
        shadow.get("reference_model", {}).get("metrics")
        if isinstance(shadow.get("reference_model"), dict)
        else {}
    )
    lines = [
        "# D48 Product-Critical Shadow Benchmark",
        "",
        f"- Dataset: `{report.get('dataset_path')}`",
        f"- Decision: `{decision.get('publish_recommendation')}`",
        f"- Selected candidate: `{decision.get('selected_candidate')}`",
        f"- Reason: `{decision.get('reason')}`",
        f"- Production artifact changed by D48: `{report.get('production_artifact', {}).get('changed_by_d48')}`",
        "",
        "## Reference Metrics",
        "",
        f"- MAE: `{reference_metrics.get('mae')}`",
        f"- Spearman: `{reference_metrics.get('spearman_mean')}`",
        f"- NDCG@10: `{reference_metrics.get('ndcg_at_10')}`",
        f"- Top-3 hit rate: `{reference_metrics.get('top_3_hit_rate')}`",
        "",
        "## Candidate Guardrails",
        "",
    ]
    comparisons = shadow.get("candidate_comparisons") if isinstance(shadow.get("candidate_comparisons"), list) else []
    product_guardrails = report.get("product_guardrails") if isinstance(report.get("product_guardrails"), dict) else {}
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            continue
        candidate_name = str(comparison.get("candidate_name") or "unknown")
        metrics = comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
        guardrails = comparison.get("guardrails") if isinstance(comparison.get("guardrails"), dict) else {}
        product = product_guardrails.get(candidate_name) if isinstance(product_guardrails.get(candidate_name), dict) else {}
        lines.extend(
            [
                f"### {candidate_name}",
                f"- Shadow gate passed: `{guardrails.get('publish_gate_passed')}`",
                f"- Product gate passed: `{product.get('passed')}`",
                f"- Rejection reasons: `{', '.join(guardrails.get('rejection_reasons') or []) or 'none'}`",
                f"- Product failed checks: `{', '.join(product.get('failed_checks') or []) or 'none'}`",
                f"- MAE: `{metrics.get('mae')}`",
                f"- Spearman: `{metrics.get('spearman_mean')}`",
                f"- NDCG@10: `{metrics.get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{metrics.get('top_3_hit_rate')}`",
            ]
        )
        for metric_name, delta in (comparison.get("metric_deltas") or {}).items():
            lines.append(f"- Delta `{metric_name}`: `{delta}`")
        feature_guardrail = product.get("feature_importance_guardrail") if isinstance(product.get("feature_importance_guardrail"), dict) else {}
        score_guardrail = product.get("score_response_guardrail") if isinstance(product.get("score_response_guardrail"), dict) else {}
        if feature_guardrail:
            lines.append(f"- Top feature: `{feature_guardrail.get('top_feature')}` (`{feature_guardrail.get('top_feature_group')}`)")
        if score_guardrail:
            lines.append(
                f"- Avg critical/supporting drop: `{score_guardrail.get('average_critical_drop')}` / `{score_guardrail.get('average_supporting_drop')}`"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "D48 is a release gate, not a training step. If the recommendation is `keep_current`, D49 should record a controlled no-publish decision instead of replacing the runtime model.",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_d48_product_shadow_benchmark(
    *,
    dataset_path: str | Path = DEFAULT_D47_DATASET_PATH,
    reference_model_path: str | Path = DEFAULT_MODEL_PATH,
    candidate_model_paths: Sequence[str | Path] = DEFAULT_D48_CANDIDATE_PATHS,
    output_dir: str | Path = DEFAULT_D48_OUTPUT_DIR,
    report_json_path: str | Path = DEFAULT_D48_REPORT_JSON_PATH,
    report_markdown_path: str | Path = DEFAULT_D48_REPORT_MD_PATH,
    smoke_queries: Sequence[str] = DEFAULT_D48_SMOKE_QUERIES,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    production_before = Path(reference_model_path).read_bytes() if Path(reference_model_path).exists() else b""
    production_sha1_before = _sha1_file(reference_model_path)
    rows = load_dataset_rows(dataset_path)
    train_rows, validation_rows, _split = split_dataset_rows(rows, test_size=test_size, random_state=random_state)
    if not train_rows or not validation_rows:
        raise ValueError("D48 split produced an empty train or validation set")
    shadow_report = run_shadow_benchmark(
        dataset_path=dataset_path,
        reference_model_path=reference_model_path,
        candidate_model_paths=candidate_model_paths,
        output_dir=output_dir,
        smoke_queries=smoke_queries,
        test_size=test_size,
        random_state=random_state,
    )
    product_guardrails = build_product_guardrails(
        shadow_report=shadow_report,
        validation_rows=validation_rows,
    )
    decision = build_d48_decision(shadow_report=shadow_report, product_guardrails=product_guardrails)
    production_after = Path(reference_model_path).read_bytes() if Path(reference_model_path).exists() else b""
    production_sha1_after = _sha1_file(reference_model_path)
    report = {
        "task": "D48",
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": shadow_report.get("dataset_version"),
        "reference_model_path": str(Path(reference_model_path)),
        "candidate_model_paths": [str(Path(path)) for path in candidate_model_paths],
        "shadow_benchmark": shadow_report,
        "product_guardrails": product_guardrails,
        "decision": decision,
        "production_artifact": {
            "path": str(Path(reference_model_path)),
            "sha1_before": production_sha1_before,
            "sha1_after": production_sha1_after,
            "changed_by_d48": production_before != production_after,
        },
        "next_step": "D49 controlled publish only if D48 recommends publish_candidate; otherwise record no-publish and keep current production.",
    }
    report["metric_deltas_by_candidate"] = {
        str(comparison.get("candidate_name")): comparison.get("metric_deltas")
        for comparison in shadow_report.get("candidate_comparisons", [])
        if isinstance(comparison, dict)
    }
    Path(report_markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_markdown_path).write_text(_render_markdown(report), encoding="utf-8")
    report["report_paths"] = {
        "json_path": str(Path(report_json_path)),
        "markdown_path": str(Path(report_markdown_path)),
        "shadow_json_path": str(Path(output_dir) / "shadow-benchmark-guardrails-report.json"),
        "shadow_markdown_path": str(Path(output_dir) / "shadow-benchmark-guardrails-report.md"),
    }
    _write_json(report_json_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D48 product-critical shadow benchmark for D47 candidates.")
    parser.add_argument("--dataset", default=str(DEFAULT_D47_DATASET_PATH))
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--candidate-model", action="append", default=[])
    parser.add_argument("--output-dir", default=str(DEFAULT_D48_OUTPUT_DIR))
    parser.add_argument("--report-json", default=str(DEFAULT_D48_REPORT_JSON_PATH))
    parser.add_argument("--report-md", default=str(DEFAULT_D48_REPORT_MD_PATH))
    parser.add_argument("--smoke-query", action="append", default=[])
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    report = run_d48_product_shadow_benchmark(
        dataset_path=args.dataset,
        reference_model_path=args.reference_model,
        candidate_model_paths=tuple(args.candidate_model or [str(path) for path in DEFAULT_D48_CANDIDATE_PATHS]),
        output_dir=args.output_dir,
        report_json_path=args.report_json,
        report_markdown_path=args.report_md,
        smoke_queries=tuple(args.smoke_query or DEFAULT_D48_SMOKE_QUERIES),
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
