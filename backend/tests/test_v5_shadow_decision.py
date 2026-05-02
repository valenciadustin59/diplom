from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.ml.model import save_model
import app.ml.v5_shadow_decision as d54
from app.ml.v5_shadow_decision import (
    build_d54_decision,
    build_d54_product_guardrails,
    run_d54_shadow_decision,
)


class ConstantModel:
    def __init__(self, value: float = 50.0) -> None:
        self.value = float(value)

    def predict(self, rows):
        return [self.value for _ in rows]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _dataset_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for query in ("query-a", "query-b"):
        for rank, score in ((1, 95), (2, 82), (3, 60), (4, 40)):
            rows.append(
                {
                    "query": query,
                    "url": f"https://example.com/{query}/{rank}",
                    "domain": "example.com",
                    "rank": rank,
                    "target_score": score,
                    "semantic_similarity": score / 100.0,
                    "word_count": 1200 + rank,
                    "fetch_status": "ok",
                    "intent": "commercial",
                    "dataset_version": "dataset-v5",
                }
            )
    return rows


def _save_test_model(path: Path, *, candidate_name: str | None = None) -> None:
    metadata = {
        "model_schema_version": "v3",
        "feature_columns": ["semantic_similarity", "word_count"],
        "dataset_version": "dataset-v5" if candidate_name else "dataset-v3-d37",
        "artifact_version": candidate_name or "dataset-v3-d37-test",
        "model_type": "ConstantModel",
        "rows_count": 8,
        "queries_count": 2,
        "domains_count": 1,
        "metrics_summary": {
            "mae": 10.0,
            "rmse": 12.0,
            "spearman_mean": 0.4,
            "ndcg_at_10": 0.9,
            "top_3_hit_rate": 0.95,
        },
    }
    if candidate_name:
        metadata.update(
            {
                "candidate_name": candidate_name,
                "candidate_family": "pointwise",
                "training_task": "D53",
                "non_production": True,
                "runtime_enabled": False,
                "publish_decision_required": "D54",
                "feature_policy_version": "v5-shortcut-control-v1",
                "feature_importance_summary": {
                    "available": True,
                    "top_features": [
                        {"feature": "semantic_similarity", "importance": 10.0},
                        {"feature": "word_count", "importance": 1.0},
                    ],
                },
            }
        )
    save_model(ConstantModel(), metrics=metadata["metrics_summary"], model_path=path, metadata=metadata)


def test_d54_decision_keeps_current_when_no_candidate_passes_product_gate() -> None:
    shadow_report = {
        "reference_model": {
            "candidate_name": "reference_artifact",
            "status": "available",
            "metrics": {
                "spearman_mean": 0.42,
                "ndcg_at_10": 0.97,
                "top_3_hit_rate": 0.95,
                "mae": 8.0,
            },
        },
        "candidates": [
            {
                "candidate_name": "hybrid_catboost_ranker_v5",
                "status": "available",
                "metrics": {
                    "spearman_mean": 0.95,
                    "ndcg_at_10": 0.998,
                    "top_3_hit_rate": 0.65,
                    "mae": 2.8,
                },
            }
        ],
    }

    decision = build_d54_decision(
        shadow_report=shadow_report,
        product_guardrails={"hybrid_catboost_ranker_v5": {"passed": False}},
    )

    assert decision["decision"] == "keep_current"
    assert decision["publish_action"] == "no_publish"
    assert decision["reason"] == "no_candidate_passed_v5_release_guardrails"


def test_d54_product_guardrail_reports_low_top3_as_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(d54, "feature_dominance_guardrail", lambda candidate: {"passed": True})
    monkeypatch.setattr(d54, "score_response_guardrail", lambda **kwargs: {"passed": True})
    monkeypatch.setattr(d54, "_prediction_bounds", lambda **kwargs: {"passed": True})
    shadow_report = {
        "candidates": [
            {
                "candidate_name": "pointwise_catboost_v5",
                "status": "available",
                "model_path": "candidate.pkl",
                "metrics": {},
            }
        ],
        "candidate_comparisons": [
            {
                "candidate_name": "pointwise_catboost_v5",
                "model_path": "candidate.pkl",
                "candidate_metrics": {
                    "mae": 1.2,
                    "ndcg_at_10": 0.998,
                    "top_3_hit_rate": 0.6,
                },
                "reference_metrics": {
                    "mae": 8.0,
                    "ndcg_at_10": 0.97,
                    "top_3_hit_rate": 0.95,
                },
                "guardrails": {"publish_gate_passed": False, "rejection_reasons": ["top_3_hit_rate_regressed"]},
            }
        ],
    }

    guardrails = build_d54_product_guardrails(shadow_report=shadow_report, validation_rows=[])

    assert guardrails["pointwise_catboost_v5"]["passed"] is True
    assert guardrails["pointwise_catboost_v5"]["failed_checks"] == []
    assert guardrails["pointwise_catboost_v5"]["base_serp_alignment_rejection_reasons"] == [
        "top_3_hit_rate_regressed"
    ]
    assert guardrails["pointwise_catboost_v5"]["serp_alignment_diagnostics"]["blocking"] is False
    assert guardrails["pointwise_catboost_v5"]["serp_alignment_diagnostics"]["warnings"] == [
        "top_3_hit_rate_below_diagnostic_floor",
        "top_3_hit_rate_below_reference",
    ]


def test_d54_decision_uses_competitiveness_metrics_without_top3_sorting() -> None:
    shadow_report = {
        "reference_model": {
            "candidate_name": "reference_artifact",
            "status": "available",
            "metrics": {
                "spearman_mean": 0.51,
                "ndcg_at_10": 0.981,
                "top_3_hit_rate": 0.9,
                "mae": 8.0,
            },
        },
        "candidates": [
            {
                "candidate_name": "legacy_aligned_candidate",
                "status": "available",
                "metrics": {
                    "spearman_mean": 0.7,
                    "ndcg_at_10": 0.99,
                    "top_3_hit_rate": 1.0,
                    "mae": 6.0,
                },
            },
            {
                "candidate_name": "product_quality_candidate",
                "status": "available",
                "metrics": {
                    "spearman_mean": 0.95,
                    "ndcg_at_10": 0.998,
                    "top_3_hit_rate": 0.6,
                    "mae": 1.2,
                },
            },
        ],
    }

    decision = build_d54_decision(
        shadow_report=shadow_report,
        product_guardrails={
            "legacy_aligned_candidate": {"passed": True},
            "product_quality_candidate": {"passed": True},
        },
    )

    assert decision["decision"] == "publish_candidate"
    assert decision["publish_action"] == "controlled_publish_required"
    assert decision["selected_candidate"] == "product_quality_candidate"


def test_run_d54_shadow_decision_writes_no_publish_report_without_mutating_production(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.controlled.csv"
    page_labels_path = tmp_path / "page_labels.csv"
    split_path = tmp_path / "split.json"
    reference_path = tmp_path / "artifacts" / "page_quality_model.pkl"
    candidate_path = tmp_path / "artifacts" / "candidate.pkl"
    output_dir = tmp_path / "d54"
    d53_report_path = tmp_path / "d53-report.json"
    rows = _dataset_rows()
    _write_csv(dataset_path, rows)
    _write_csv(
        page_labels_path,
        [
            {
                "query": row["query"],
                "url": row["url"],
                "target_score": row["target_score"],
                "page_target_score": row["target_score"],
                "ranking_target_score": row["target_score"],
            }
            for row in rows
        ],
    )
    split_path.write_text(
        json.dumps(
            {
                "split_mode": "group_by_query",
                "train_queries": ["query-a"],
                "validation_queries": ["query-b"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    d53_report_path.write_text(json.dumps({"task": "D53"}, ensure_ascii=False), encoding="utf-8")
    _save_test_model(reference_path)
    _save_test_model(candidate_path, candidate_name="pointwise_catboost_v5")
    before = reference_path.read_bytes()

    report = run_d54_shadow_decision(
        dataset_path=dataset_path,
        split_path=split_path,
        page_labels_path=page_labels_path,
        d53_report_path=d53_report_path,
        reference_model_path=reference_path,
        candidate_model_paths=(candidate_path,),
        output_dir=output_dir,
        report_json_path=output_dir / "d54.json",
        report_markdown_path=output_dir / "d54.md",
        check_results=[{"name": "pytest", "status": "passed"}],
    )

    assert reference_path.read_bytes() == before
    assert report["decision"]["decision"] == "keep_current"
    assert report["decision"]["publish_action"] == "no_publish"
    assert report["production_artifact"]["changed_by_d54"] is False
    assert report["verification"]["status"] == "passed"
    assert Path(report["report_paths"]["json_path"]).exists()
    assert "# D54 Shadow Benchmark And Controlled Decision" in Path(report["report_paths"]["markdown_path"]).read_text(
        encoding="utf-8"
    )
