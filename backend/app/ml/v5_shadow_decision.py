from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.ml.competitiveness_release_policy import (
    COMPETITIVENESS_RELEASE_POLICY_VERSION,
    DEFAULT_ABSOLUTE_ERROR_TOLERANCE_RATIO,
    DEFAULT_MAX_NDCG_REGRESSION,
    DEFAULT_MAX_SPEARMAN_REGRESSION,
    DEFAULT_TOP3_DIAGNOSTIC_FLOOR,
    build_competitiveness_release_scorecard,
    competitiveness_candidate_sort_key,
)
from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact, load_saved_model
from app.ml.no_publish_decision import build_production_artifact_state, build_versioned_reference_state, sha1_file
from app.ml.publish import ARTIFACTS_DIR, build_artifact_metadata_path
from app.ml.shadow_benchmark import (
    _apply_explainability_sensibility_guardrails,
    _apply_runtime_explanation_guardrails,
    _serialize_shadow_model,
    build_candidate_guardrails,
    build_metric_deltas,
    build_shadow_decision,
    build_smoke_explainability_summary,
    evaluate_shadow_artifact,
)
from app.ml.shadow_explainability import build_explainability_sensibility_summary
from app.ml.shadow_report import write_shadow_benchmark_report
from app.ml.train import candidate_sort_key, load_dataset_rows, rows_to_matrix
from app.ml.v3_dataset import DATASET_VERSIONS_DIR
from app.ml.v5_candidate_training import (
    DEFAULT_DATASET_VERSION,
    DEFAULT_D53_HYBRID_CANDIDATE_PATH,
    DEFAULT_D53_POINTWISE_CANDIDATE_PATH,
    DEFAULT_D53_RANKING_CANDIDATE_PATH,
    DEFAULT_D53_REPORT_JSON_PATH,
    V5CalibratedRankerModel,
    V5HybridRankerModel,
    attach_v5_targets,
    split_rows_from_manifest,
)
from app.ml.v5_feature_policy import (
    DEFAULT_CONTROLLED_DATASET_PATH,
    FEATURE_POLICY_VERSION_V5,
    feature_dominance_guardrail,
    score_response_guardrail,
)
from app.ml.v5_preferences import DEFAULT_OUTPUT_PAGE_LABELS_PATH


DEFAULT_D54_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v5-d54"
DEFAULT_D54_REPORT_JSON_PATH = DEFAULT_D54_OUTPUT_DIR / "d54-shadow-decision-report.json"
DEFAULT_D54_REPORT_MD_PATH = DEFAULT_D54_OUTPUT_DIR / "d54-shadow-decision-report.md"
DEFAULT_D54_SHADOW_OUTPUT_DIR = DEFAULT_D54_OUTPUT_DIR
DEFAULT_D54_CANDIDATE_PATHS = (
    DEFAULT_D53_POINTWISE_CANDIDATE_PATH,
    DEFAULT_D53_RANKING_CANDIDATE_PATH,
    DEFAULT_D53_HYBRID_CANDIDATE_PATH,
)
DEFAULT_SPLIT_PATH = DATASET_VERSIONS_DIR / DEFAULT_DATASET_VERSION / "split.json"
TOP3_HIT_RATE_DIAGNOSTIC_FLOOR = DEFAULT_TOP3_DIAGNOSTIC_FLOOR
MAX_SPEARMAN_MEANINGFUL_REGRESSION = DEFAULT_MAX_SPEARMAN_REGRESSION
MAX_NDCG_MEANINGFUL_REGRESSION = DEFAULT_MAX_NDCG_REGRESSION
ABSOLUTE_ERROR_TOLERANCE_RATIO = DEFAULT_ABSOLUTE_ERROR_TOLERANCE_RATIO


def _read_json(path: str | Path) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _page_label_targets(path: str | Path = DEFAULT_OUTPUT_PAGE_LABELS_PATH) -> dict[tuple[str, str], dict[str, float]]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    targets: dict[tuple[str, str], dict[str, float]] = {}
    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            query = str(row.get("query") or "").strip()
            url = str(row.get("url") or "").strip()
            if not query or not url:
                continue
            targets[(query, url)] = {
                "page_target_score": _safe_float(row.get("page_target_score"), _safe_float(row.get("target_score"))),
                "ranking_target_score": _safe_float(row.get("ranking_target_score"), _safe_float(row.get("target_score"))),
            }
    return targets


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _selected_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("rmse", "mae", "spearman_mean", "ndcg_at_10", "top_3_hit_rate", "validation_queries")
    return {key: metrics[key] for key in keys if key in metrics}


def _model_name(entry: Mapping[str, Any]) -> str:
    return str(entry.get("candidate_name") or Path(str(entry.get("model_path") or "model")).stem)


def _metadata_sidecar(path: str | Path) -> dict[str, Any]:
    metadata_path = build_artifact_metadata_path(path)
    return _read_json(metadata_path)


def _saved_feature_importance(path: str | Path) -> dict[str, Any]:
    raw_payload = load_saved_model(path) or {}
    raw_importance = raw_payload.get("feature_importance_summary")
    if isinstance(raw_importance, dict) and raw_importance.get("available"):
        return dict(raw_importance)
    sidecar_importance = _metadata_sidecar(path).get("feature_importance_summary")
    if isinstance(sidecar_importance, dict) and sidecar_importance.get("available"):
        return dict(sidecar_importance)
    artifact = load_model_artifact(path) or {}
    artifact_importance = artifact.get("feature_importance_summary")
    if isinstance(artifact_importance, dict) and artifact_importance.get("available"):
        return dict(artifact_importance)
    return {}


def _enrich_candidate_from_saved_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    model_path = candidate.get("model_path")
    if not model_path:
        return candidate
    raw_payload = load_saved_model(model_path) or {}
    sidecar = _metadata_sidecar(model_path)
    current_importance = candidate.get("feature_importance_summary")
    if not (isinstance(current_importance, dict) and current_importance.get("available")):
        saved_importance = _saved_feature_importance(model_path)
        if saved_importance:
            candidate["feature_importance_summary"] = saved_importance
    candidate["artifact_metadata"] = {
        "training_task": raw_payload.get("training_task") or sidecar.get("training_task"),
        "non_production": raw_payload.get("non_production", sidecar.get("non_production")),
        "runtime_enabled": raw_payload.get("runtime_enabled", sidecar.get("runtime_enabled")),
        "publish_decision_required": raw_payload.get("publish_decision_required")
        or sidecar.get("publish_decision_required"),
        "feature_policy_version": raw_payload.get("feature_policy_version")
        or sidecar.get("feature_policy_version"),
        "training_target": raw_payload.get("training_target") or sidecar.get("training_target"),
        "training_report_path": raw_payload.get("training_report_path") or sidecar.get("training_report_path"),
    }
    return candidate


def build_d54_validation_rows(
    *,
    dataset_path: str | Path = DEFAULT_CONTROLLED_DATASET_PATH,
    split_path: str | Path = DEFAULT_SPLIT_PATH,
    page_labels_path: str | Path = DEFAULT_OUTPUT_PAGE_LABELS_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    rows = attach_v5_targets(load_dataset_rows(dataset_path), _page_label_targets(page_labels_path))
    if len(rows) < 4:
        raise ValueError("D54 requires at least 4 dataset rows")
    train_rows, validation_rows, split = split_rows_from_manifest(
        rows,
        _read_json(split_path),
        test_size=test_size,
        random_state=random_state,
    )
    if not train_rows or not validation_rows:
        raise ValueError("D54 split produced an empty train or validation set")
    return train_rows, validation_rows, split


def _default_smoke_queries(validation_rows: Sequence[Mapping[str, str]], limit: int = 4) -> tuple[str, ...]:
    queries: list[str] = []
    seen: set[str] = set()
    for row in validation_rows:
        query = str(row.get("query") or "").strip()
        if query and query not in seen:
            seen.add(query)
            queries.append(query)
        if len(queries) >= limit:
            break
    return tuple(queries)


def _prediction_bounds(*, model_path: str | Path, rows: Sequence[dict[str, str]]) -> dict[str, Any]:
    artifact = load_model_artifact(model_path)
    if artifact is None:
        return {
            "passed": False,
            "reason": "artifact_not_available",
            "rows_count": 0,
        }
    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), (list, tuple)) else None
    matrix, _ = rows_to_matrix([dict(row) for row in rows], feature_columns=feature_columns)
    predictions = [float(value) for value in artifact["model"].predict(matrix)]
    below_zero = sum(1 for value in predictions if value < 0.0)
    above_hundred = sum(1 for value in predictions if value > 100.0)
    return {
        "passed": bool(predictions) and below_zero == 0 and above_hundred == 0,
        "rows_count": len(predictions),
        "min_score": round(min(predictions), 6) if predictions else None,
        "max_score": round(max(predictions), 6) if predictions else None,
        "below_zero_count": below_zero,
        "above_hundred_count": above_hundred,
    }


def _comparison_by_name(shadow_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    comparisons = shadow_report.get("candidate_comparisons")
    return {
        str(comparison.get("candidate_name")): comparison
        for comparison in (comparisons if isinstance(comparisons, list) else [])
        if isinstance(comparison, dict)
    }


def _candidate_by_name(shadow_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = shadow_report.get("candidates")
    return {
        _model_name(candidate): candidate
        for candidate in (candidates if isinstance(candidates, list) else [])
        if isinstance(candidate, dict) and candidate.get("status") == "available"
    }


def build_d54_shadow_benchmark(
    *,
    rows: Sequence[dict[str, str]],
    train_rows: Sequence[dict[str, str]],
    validation_rows: Sequence[dict[str, str]],
    split_metadata: Mapping[str, Any],
    dataset_path: str | Path = DEFAULT_CONTROLLED_DATASET_PATH,
    reference_model_path: str | Path = DEFAULT_MODEL_PATH,
    candidate_model_paths: Sequence[str | Path] = DEFAULT_D54_CANDIDATE_PATHS,
    output_dir: str | Path | None = DEFAULT_D54_SHADOW_OUTPUT_DIR,
    smoke_queries: Sequence[str] | None = None,
) -> dict[str, Any]:
    reference_model = evaluate_shadow_artifact(
        candidate_name="reference_artifact",
        candidate_family="production",
        model_path=reference_model_path,
        validation_rows=[dict(row) for row in validation_rows],
    )
    if reference_model.get("status") != "available":
        raise ValueError(f"Reference model is not available: {reference_model_path}")

    candidates = [
        _enrich_candidate_from_saved_payload(
            evaluate_shadow_artifact(
                candidate_name=Path(candidate_path).stem,
                candidate_family="candidate",
                model_path=candidate_path,
                validation_rows=[dict(row) for row in validation_rows],
            )
        )
        for candidate_path in candidate_model_paths
    ]
    resolved_smoke_queries = tuple(smoke_queries or _default_smoke_queries(validation_rows))
    smoke_summary = build_smoke_explainability_summary(
        rows=[dict(row) for row in rows],
        reference_model=reference_model,
        candidates=candidates,
        smoke_queries=resolved_smoke_queries,
    )
    _apply_runtime_explanation_guardrails(candidates, smoke_summary)
    sensibility_summary = build_explainability_sensibility_summary(
        candidates=candidates,
        smoke_summary=smoke_summary,
    )
    _apply_explainability_sensibility_guardrails(candidates, sensibility_summary)
    comparisons = [
        {
            "candidate_name": str(candidate.get("candidate_name") or "unknown"),
            "candidate_family": str(candidate.get("candidate_family") or "unknown"),
            "model_path": candidate.get("model_path"),
            "candidate_metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
            "reference_metrics": reference_model.get("metrics") if isinstance(reference_model.get("metrics"), dict) else {},
            "metric_deltas": build_metric_deltas(
                candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
                reference_model.get("metrics") if isinstance(reference_model.get("metrics"), dict) else {},
            ),
            "guardrails": build_candidate_guardrails(candidate, reference_model),
        }
        for candidate in candidates
    ]
    available_candidates = [candidate for candidate in candidates if candidate.get("status") == "available"]
    best_candidate = max(available_candidates, key=candidate_sort_key) if available_candidates else None
    split_summary = {
        **dict(split_metadata),
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "train_queries_count": len({str(row.get("query") or "") for row in train_rows}),
        "validation_queries_count": len({str(row.get("query") or "") for row in validation_rows}),
    }
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D54-shadow",
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": DEFAULT_DATASET_VERSION,
        "feature_policy_version": FEATURE_POLICY_VERSION_V5,
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "split": split_summary,
        "reference_model": _serialize_shadow_model(reference_model),
        "candidates": [_serialize_shadow_model(candidate) | {"artifact_metadata": candidate.get("artifact_metadata")} for candidate in candidates],
        "candidate_comparisons": comparisons,
        "best_candidate_by_ranking_metrics": _serialize_shadow_model(best_candidate) if best_candidate is not None else None,
        "smoke_explainability": smoke_summary,
        "explainability_sensibility": sensibility_summary,
        "decision": build_shadow_decision(
            reference_model=reference_model,
            candidates=candidates,
            comparisons=comparisons,
        ),
    }
    if output_dir is not None:
        report["report_paths"] = write_shadow_benchmark_report(report, output_dir)
    return report


def build_d54_product_guardrails(
    *,
    shadow_report: Mapping[str, Any],
    validation_rows: Sequence[dict[str, str]],
    top3_diagnostic_floor: float = TOP3_HIT_RATE_DIAGNOSTIC_FLOOR,
    max_spearman_regression: float = MAX_SPEARMAN_MEANINGFUL_REGRESSION,
    max_ndcg_regression: float = MAX_NDCG_MEANINGFUL_REGRESSION,
    absolute_error_tolerance_ratio: float = ABSOLUTE_ERROR_TOLERANCE_RATIO,
) -> dict[str, Any]:
    candidates = _candidate_by_name(shadow_report)
    comparisons = _comparison_by_name(shadow_report)
    guardrails: dict[str, Any] = {}
    for candidate_name, candidate in candidates.items():
        comparison = comparisons.get(candidate_name, {})
        base_guardrails = comparison.get("guardrails") if isinstance(comparison.get("guardrails"), dict) else {}
        candidate_metrics = comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
        reference_metrics = comparison.get("reference_metrics") if isinstance(comparison.get("reference_metrics"), dict) else {}
        feature_dominance = feature_dominance_guardrail(candidate)
        model_path = str(candidate.get("model_path") or "")
        score_response = score_response_guardrail(model_path=model_path, rows=validation_rows) if model_path else {
            "passed": False,
            "failed_checks": ["model_path_missing"],
        }
        bounds = _prediction_bounds(model_path=model_path, rows=validation_rows) if model_path else {
            "passed": False,
            "failed_checks": ["model_path_missing"],
        }
        guardrails[candidate_name] = build_competitiveness_release_scorecard(
            candidate_name=candidate_name,
            candidate_metrics=candidate_metrics,
            reference_metrics=reference_metrics,
            base_guardrails=base_guardrails,
            feature_dominance=feature_dominance,
            score_response=score_response,
            prediction_bounds=bounds,
            max_spearman_regression=max_spearman_regression,
            max_ndcg_regression=max_ndcg_regression,
            absolute_error_tolerance_ratio=absolute_error_tolerance_ratio,
            top3_diagnostic_floor=top3_diagnostic_floor,
        )
    return guardrails


def build_d54_decision(
    *,
    shadow_report: Mapping[str, Any],
    product_guardrails: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = _candidate_by_name(shadow_report)
    if not candidates:
        return {
            "decision": "needs_more_data",
            "publish_action": "no_publish",
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
            "decision": "keep_current",
            "publish_action": "no_publish",
            "publish_recommendation": "keep_current",
            "selected_candidate": None,
            "reason": "no_candidate_passed_v5_release_guardrails",
        }
    reference_model = shadow_report.get("reference_model") if isinstance(shadow_report.get("reference_model"), dict) else {}
    selected = max((candidates[name] for name in eligible_names), key=competitiveness_candidate_sort_key)
    if competitiveness_candidate_sort_key(selected) <= competitiveness_candidate_sort_key(reference_model):
        return {
            "decision": "keep_current",
            "publish_action": "no_publish",
            "publish_recommendation": "keep_current",
            "selected_candidate": _model_name(selected),
            "reason": "best_v5_gate_passing_candidate_does_not_outperform_current",
        }
    return {
        "decision": "publish_candidate",
        "publish_action": "controlled_publish_required",
        "publish_recommendation": "publish_candidate",
        "selected_candidate": _model_name(selected),
        "reason": "candidate_passed_v5_release_guardrails_and_outperformed_current",
    }


def _verification_summary(check_results: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    checks = [dict(check) for check in (check_results or [])]
    if not checks:
        return {"status": "pending", "checks": [], "reason": "checks_not_recorded"}
    failed = [check for check in checks if check.get("status") != "passed"]
    return {"status": "passed" if not failed else "failed", "checks": checks}


def _summarize_candidate_decisions(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    shadow = report.get("shadow_benchmark") if isinstance(report.get("shadow_benchmark"), dict) else {}
    comparisons = _comparison_by_name(shadow)
    product_guardrails = report.get("product_guardrails") if isinstance(report.get("product_guardrails"), dict) else {}
    summaries: list[dict[str, Any]] = []
    for candidate_name, guardrail in product_guardrails.items():
        if not isinstance(guardrail, dict):
            continue
        comparison = comparisons.get(str(candidate_name), {})
        candidate_metrics = comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
        reference_metrics = comparison.get("reference_metrics") if isinstance(comparison.get("reference_metrics"), dict) else {}
        feature = guardrail.get("feature_dominance_guardrail") if isinstance(guardrail.get("feature_dominance_guardrail"), dict) else {}
        response = guardrail.get("score_response_guardrail") if isinstance(guardrail.get("score_response_guardrail"), dict) else {}
        bounds = guardrail.get("prediction_bounds") if isinstance(guardrail.get("prediction_bounds"), dict) else {}
        serp = (
            guardrail.get("serp_alignment_diagnostics")
            if isinstance(guardrail.get("serp_alignment_diagnostics"), dict)
            else {}
        )
        recommendation = (
            guardrail.get("recommendation_consistency")
            if isinstance(guardrail.get("recommendation_consistency"), dict)
            else {}
        )
        summaries.append(
            {
                "candidate_name": str(candidate_name),
                "model_path": comparison.get("model_path"),
                "publish_allowed": bool(guardrail.get("passed")),
                "failed_checks": list(guardrail.get("failed_checks") or []),
                "base_rejection_reasons": list(guardrail.get("base_rejection_reasons") or []),
                "base_page_quality_rejection_reasons": list(
                    guardrail.get("base_page_quality_rejection_reasons") or []
                ),
                "base_serp_alignment_rejection_reasons": list(
                    guardrail.get("base_serp_alignment_rejection_reasons") or []
                ),
                "candidate_metrics": _selected_metrics(candidate_metrics),
                "reference_metrics": _selected_metrics(reference_metrics),
                "metric_deltas": _selected_metrics(
                    comparison.get("metric_deltas") if isinstance(comparison.get("metric_deltas"), dict) else {}
                ),
                "metric_groups": guardrail.get("metric_groups"),
                "serp_alignment_warnings": list(serp.get("warnings") or []),
                "recommendation_consistency": {
                    "contract_version": recommendation.get("contract_version"),
                    "status": recommendation.get("status"),
                    "passed": recommendation.get("passed"),
                    "blocking": recommendation.get("blocking"),
                },
                "top_feature": feature.get("top_feature"),
                "top_feature_group": feature.get("top_feature_group"),
                "feature_guardrail_passed": bool(feature.get("passed")),
                "score_response_guardrail_passed": bool(response.get("passed")),
                "average_critical_drop": response.get("average_critical_drop"),
                "average_supporting_drop": response.get("average_supporting_drop"),
                "prediction_bounds": {
                    "passed": bounds.get("passed"),
                    "min_score": bounds.get("min_score"),
                    "max_score": bounds.get("max_score"),
                },
            }
        )
    return summaries


def _inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_d54_markdown(report: Mapping[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    production = report.get("production_artifact") if isinstance(report.get("production_artifact"), dict) else {}
    shadow = report.get("shadow_benchmark") if isinstance(report.get("shadow_benchmark"), dict) else {}
    reference_metrics = (
        shadow.get("reference_model", {}).get("metrics")
        if isinstance(shadow.get("reference_model"), dict)
        else {}
    )
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    lines = [
        "# D54 Shadow Benchmark And Controlled Decision",
        "",
        f"- Decision: `{decision.get('decision')}`",
        f"- Publish action: `{decision.get('publish_action')}`",
        f"- Reason: `{decision.get('reason')}`",
        f"- Selected candidate: `{decision.get('selected_candidate')}`",
        f"- Dataset: `{report.get('dataset_path')}`",
        f"- Feature policy: `{report.get('feature_policy_version')}`",
        f"- Release policy: `{report.get('release_policy_version')}`",
        f"- Production SHA1 before: `{production.get('sha1_before')}`",
        f"- Production SHA1 after: `{production.get('sha1_after')}`",
        f"- Production changed by D54: `{production.get('changed_by_d54')}`",
        "",
        "## Current Production Reference",
        "",
        f"- Metrics: `{_inline_json(_selected_metrics(reference_metrics if isinstance(reference_metrics, dict) else {}))}`",
        "",
        "## Candidate Decisions",
        "",
    ]
    for candidate in report.get("candidate_decisions", []):
        if not isinstance(candidate, dict):
            continue
        lines.extend(
            [
                f"### {candidate.get('candidate_name')}",
                f"- Publish allowed: `{candidate.get('publish_allowed')}`",
                f"- Failed checks: `{', '.join(candidate.get('failed_checks') or []) or 'none'}`",
                f"- Base rejection reasons: `{', '.join(candidate.get('base_rejection_reasons') or []) or 'none'}`",
                f"- SERP alignment warnings: `{', '.join(candidate.get('serp_alignment_warnings') or []) or 'none'}`",
                f"- Candidate metrics: `{_inline_json(candidate.get('candidate_metrics'))}`",
                f"- Metric deltas: `{_inline_json(candidate.get('metric_deltas'))}`",
                f"- Metric groups: `{_inline_json(candidate.get('metric_groups'))}`",
                f"- Recommendation consistency: `{_inline_json(candidate.get('recommendation_consistency'))}`",
                f"- Top feature: `{candidate.get('top_feature')}` (`{candidate.get('top_feature_group')}`)",
                f"- Critical/supporting drop: `{candidate.get('average_critical_drop')}` / `{candidate.get('average_supporting_drop')}`",
                f"- Prediction bounds: `{_inline_json(candidate.get('prediction_bounds'))}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Verification",
            "",
            f"- Overall status: `{verification.get('status')}`",
        ]
    )
    for check in verification.get("checks", []):
        if isinstance(check, dict):
            lines.append(f"- `{check.get('name')}`: `{check.get('status')}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "D54 is a release gate. If the decision is `keep_current`, D53 artifacts remain non-production evidence and the active runtime artifact is unchanged.",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_d54_shadow_decision(
    *,
    dataset_path: str | Path = DEFAULT_CONTROLLED_DATASET_PATH,
    split_path: str | Path = DEFAULT_SPLIT_PATH,
    page_labels_path: str | Path = DEFAULT_OUTPUT_PAGE_LABELS_PATH,
    d53_report_path: str | Path = DEFAULT_D53_REPORT_JSON_PATH,
    reference_model_path: str | Path = DEFAULT_MODEL_PATH,
    candidate_model_paths: Sequence[str | Path] = DEFAULT_D54_CANDIDATE_PATHS,
    output_dir: str | Path = DEFAULT_D54_OUTPUT_DIR,
    report_json_path: str | Path = DEFAULT_D54_REPORT_JSON_PATH,
    report_markdown_path: str | Path = DEFAULT_D54_REPORT_MD_PATH,
    smoke_queries: Sequence[str] | None = None,
    check_results: Sequence[Mapping[str, Any]] | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    production_sha1_before = sha1_file(reference_model_path)
    rows = attach_v5_targets(load_dataset_rows(dataset_path), _page_label_targets(page_labels_path))
    train_rows, validation_rows, split_metadata = split_rows_from_manifest(
        rows,
        _read_json(split_path),
        test_size=test_size,
        random_state=random_state,
    )
    if not train_rows or not validation_rows:
        raise ValueError("D54 split produced an empty train or validation set")
    shadow_report = build_d54_shadow_benchmark(
        rows=rows,
        train_rows=train_rows,
        validation_rows=validation_rows,
        split_metadata=split_metadata,
        dataset_path=dataset_path,
        reference_model_path=reference_model_path,
        candidate_model_paths=candidate_model_paths,
        output_dir=output_dir,
        smoke_queries=smoke_queries,
    )
    product_guardrails = build_d54_product_guardrails(
        shadow_report=shadow_report,
        validation_rows=validation_rows,
    )
    decision = build_d54_decision(shadow_report=shadow_report, product_guardrails=product_guardrails)
    production_state = build_production_artifact_state(reference_model_path)
    production_sha1_after = sha1_file(reference_model_path)
    if production_sha1_before != production_sha1_after:
        raise RuntimeError(
            f"Production artifact changed while generating D54 evidence: "
            f"{production_sha1_before} -> {production_sha1_after}"
        )
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D54",
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": DEFAULT_DATASET_VERSION,
        "split_path": str(Path(split_path)),
        "page_labels_path": str(Path(page_labels_path)),
        "d53_report_path": str(Path(d53_report_path)),
        "feature_policy_version": FEATURE_POLICY_VERSION_V5,
        "release_policy_version": COMPETITIVENESS_RELEASE_POLICY_VERSION,
        "reference_model_path": str(Path(reference_model_path)),
        "candidate_model_paths": [str(Path(path)) for path in candidate_model_paths],
        "shadow_benchmark": shadow_report,
        "product_guardrails": product_guardrails,
        "decision": decision,
        "candidate_decisions": [],
        "production_artifact": {
            "path": str(Path(reference_model_path)),
            "sha1_before": production_sha1_before,
            "sha1_after": production_sha1_after,
            "changed_by_d54": False,
            "selected_runtime_artifact": production_state,
        },
        "rollback_reference": build_versioned_reference_state(production_state),
        "d53_training_evidence": _read_json(d53_report_path),
        "verification": _verification_summary(check_results),
        "invariants": {
            "production_model_path": production_state["model_path"],
            "production_model_sha1": production_state["model_sha1"],
            "candidate_artifacts_are_not_runtime_selected": decision.get("publish_action") == "no_publish",
            "next_modeling_step_requires_new_task": decision.get("publish_action") == "no_publish",
        },
    }
    report["candidate_decisions"] = _summarize_candidate_decisions(report)
    report_paths = {"json_path": str(Path(report_json_path)), "markdown_path": str(Path(report_markdown_path))}
    report["report_paths"] = report_paths
    _write_json(report_json_path, report)
    Path(report_markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_markdown_path).write_text(render_d54_markdown(report), encoding="utf-8")
    return report


def _parse_check_result(value: str) -> dict[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Check result must use NAME=STATUS format.")
    name, status = value.split("=", 1)
    if not name.strip() or not status.strip():
        raise argparse.ArgumentTypeError("Check result must use non-empty NAME=STATUS format.")
    return {"name": name.strip(), "status": status.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D54 shadow benchmark and controlled decision for v5 candidates.")
    parser.add_argument("--dataset", default=str(DEFAULT_CONTROLLED_DATASET_PATH))
    parser.add_argument("--split", default=str(DEFAULT_SPLIT_PATH))
    parser.add_argument("--page-labels", default=str(DEFAULT_OUTPUT_PAGE_LABELS_PATH))
    parser.add_argument("--d53-report", default=str(DEFAULT_D53_REPORT_JSON_PATH))
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--candidate-model", action="append", default=[])
    parser.add_argument("--output-dir", default=str(DEFAULT_D54_OUTPUT_DIR))
    parser.add_argument("--report-json", default=str(DEFAULT_D54_REPORT_JSON_PATH))
    parser.add_argument("--report-md", default=str(DEFAULT_D54_REPORT_MD_PATH))
    parser.add_argument("--smoke-query", action="append", default=[])
    parser.add_argument("--check", action="append", type=_parse_check_result, default=[])
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    report = run_d54_shadow_decision(
        dataset_path=args.dataset,
        split_path=args.split,
        page_labels_path=args.page_labels,
        d53_report_path=args.d53_report,
        reference_model_path=args.reference_model,
        candidate_model_paths=tuple(args.candidate_model or [str(path) for path in DEFAULT_D54_CANDIDATE_PATHS]),
        output_dir=args.output_dir,
        report_json_path=args.report_json,
        report_markdown_path=args.report_md,
        smoke_queries=tuple(args.smoke_query) if args.smoke_query else None,
        check_results=args.check,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
