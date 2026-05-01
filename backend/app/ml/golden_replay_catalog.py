from __future__ import annotations

import json
from typing import Any

DEFAULT_RUNTIME_MODEL_INFO = {
    "source": "local_dataset",
    "model_type": "CatBoostRegressor",
    "model_schema_version": "v3",
    "artifact_version": "dataset-v3-d37-20260501200434",
    "artifact_family": "page_quality_model",
    "dataset_version": "dataset-v3-d37",
    "feature_count": 148,
}
DEFAULT_ROLLBACK_REFERENCE = {
    "label": "D38 rollback reference",
    "model_schema_version": "v1",
    "dataset_version": "ru_commercial_dataset-20260421-primary",
    "artifact_sha1": "5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9",
}
SYNTHETIC_FIXTURE_NOTE = (
    "Synthetic deterministic D41 stored fixture for guardrail coverage; "
    "not produced by a live replay audit."
)


def _deepcopy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def default_golden_query_catalog() -> list[dict[str, Any]]:
    return _deepcopy_json(
        [
            {
                "id": "renovation-moscow",
                "query": "ремонт квартир москва",
                "target_url": "https://smartremontmsk.ru/",
                "domain": "home_services",
                "description": "D38 post-publish smoke domain for commercial service pages.",
            },
            {
                "id": "plastic-windows-ekaterinburg",
                "query": "пластиковые окна екатеринбург",
                "target_url": "https://example.com/plastic-windows-ekaterinburg",
                "domain": "home_services",
                "description": "Commercial local-service query used throughout API and recommendation tests.",
            },
            {
                "id": "seo-audit",
                "query": "seo audit",
                "target_url": "https://example.com/seo-audit",
                "domain": "seo_services",
                "description": "Generic SEO-audit product query used in backend and frontend regression tests.",
            },
        ]
    )


def default_stored_replay_evidence() -> list[dict[str, Any]]:
    return _deepcopy_json(
        [
            {
                "id": "renovation-moscow",
                "evidence_kind": "stored_smoke_artifact",
                "evidence_source": "output/runtime-smoke/d38-smoke-summary.json",
                "audit_id": "690504f2-ca2f-42a6-a012-e622438437a7",
                "status": "completed",
                "score": 83.7366,
                "competitors_found": 2,
                "competitors_analyzed": 2,
                "competitors_failed": 0,
                "recommendations_count": 11,
                "warnings": [],
                "failure_context": None,
                "model_info": DEFAULT_RUNTIME_MODEL_INFO,
                "reference": {
                    **DEFAULT_ROLLBACK_REFERENCE,
                    "score": 69.5249,
                    "source": "D31 clean runtime smoke",
                },
            },
            {
                "id": "plastic-windows-ekaterinburg",
                "evidence_kind": "synthetic_stored_fixture",
                "evidence_source": "app.ml.golden_replay_catalog.default_stored_replay_evidence",
                "fixture_note": SYNTHETIC_FIXTURE_NOTE,
                "audit_id": "stored-d41-plastic-windows-ekaterinburg",
                "status": "completed",
                "score": 78.4,
                "competitors_found": 3,
                "competitors_analyzed": 2,
                "competitors_failed": 1,
                "recommendations_count": 9,
                "warnings": [],
                "failure_context": None,
                "model_info": DEFAULT_RUNTIME_MODEL_INFO,
                "reference": {**DEFAULT_ROLLBACK_REFERENCE, "score": 71.0, "source": "stored rollback expectation"},
            },
            {
                "id": "seo-audit",
                "evidence_kind": "synthetic_stored_fixture",
                "evidence_source": "app.ml.golden_replay_catalog.default_stored_replay_evidence",
                "fixture_note": SYNTHETIC_FIXTURE_NOTE,
                "audit_id": "stored-d41-seo-audit",
                "status": "completed",
                "score": 62.8,
                "competitors_found": 2,
                "competitors_analyzed": 1,
                "competitors_failed": 1,
                "recommendations_count": 7,
                "warnings": [],
                "failure_context": None,
                "model_info": DEFAULT_RUNTIME_MODEL_INFO,
                "reference": {**DEFAULT_ROLLBACK_REFERENCE, "score": 58.2, "source": "stored rollback expectation"},
            },
        ]
    )
