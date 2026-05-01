import pytest
from app.celery_app import AUDIT_QUEUES
from app.config import Settings
from app.health import check_celery_worker_health, collect_worker_runtime_metrics
from app.worker_topology import build_worker_topology_contract, evaluate_worker_topology
def test_worker_topology_contract_covers_all_audit_queues():
    contract = build_worker_topology_contract()
    assert [profile["name"] for profile in contract["profiles"]] == ["pipeline", "network", "heavy_analysis", "cpu_ml"]
    assert sorted(queue_name for profile in contract["profiles"] for queue_name in profile["queues"]) == sorted(AUDIT_QUEUES)
def test_evaluate_worker_topology_accepts_split_workers_within_same_profile():
    payload = evaluate_worker_topology(
        {
            "celery@pipeline": ["audits.pipeline"],
            "celery@network-fetch": ["audits.fetch"],
            "celery@network-competitors": ["audits.competitors", "audits.competitor_pages"],
            "celery@heavy": ["audits.heavy_analysis"],
            "celery@cpu": ["audits.features", "audits.scoring", "audits.recommendations", "audits.finalize"],
        }
    )
    assert payload["status"] == "ok"
    assert payload["missing_queues"] == []
    assert payload["invalid_workers"] == []
    assert payload["profiles"]["network"]["worker_count"] == 2
    assert payload["profiles"]["network"]["covered_queues"] == [
        "audits.competitor_pages",
        "audits.competitors",
        "audits.fetch",
    ]
    assert payload["worker_profiles"]["celery@network-fetch"]["profile_name"] == "network"
def test_evaluate_worker_topology_rejects_cross_profile_queue_affinity():
    payload = evaluate_worker_topology(
        {
            "celery@mixed": ["audits.pipeline", "audits.fetch"],
            "celery@cpu": ["audits.features", "audits.scoring", "audits.recommendations", "audits.finalize"],
        }
    )
    assert payload["status"] == "error"
    assert payload["invalid_workers"] == ["celery@mixed"]
    assert payload["worker_profiles"]["celery@mixed"]["reason"] == "cross_profile_queue_affinity"
    assert "pipeline" in payload["profiles_with_missing_queues"]
    assert "network" in payload["profiles_with_missing_queues"]
def test_collect_worker_runtime_metrics_reports_valid_topology(monkeypatch: pytest.MonkeyPatch):
    class FakeInspect:
        def stats(self):
            return {
                "pipeline@test": {"pid": 1001, "pool": {"max-concurrency": 1}},
                "network@test": {"pid": 1002, "pool": {"max-concurrency": 4}},
                "heavy@test": {"pid": 1003, "pool": {"max-concurrency": 2}},
                "cpu@test": {"pid": 1004, "pool": {"max-concurrency": 2}},
            }
        def active(self):
            return {
                "pipeline@test": [],
                "network@test": [{"name": "app.process_audit_fetch_target"}],
                "heavy@test": [{"name": "app.process_audit_run_heavy_analysis"}],
                "cpu@test": [],
            }
        def reserved(self):
            return {
                "pipeline@test": [],
                "network@test": [],
                "heavy@test": [],
                "cpu@test": [{"name": "app.process_audit_score_target"}],
            }
        def scheduled(self):
            return {
                "pipeline@test": [],
                "network@test": [],
                "heavy@test": [],
                "cpu@test": [{"request": {"name": "app.process_audit_finalize"}}],
            }
        def active_queues(self):
            return {
                "pipeline@test": [{"name": "audits.pipeline"}],
                "network@test": [
                    {"name": "audits.fetch"},
                    {"name": "audits.competitors"},
                    {"name": "audits.competitor_pages"},
                ],
                "heavy@test": [{"name": "audits.heavy_analysis"}],
                "cpu@test": [
                    {"name": "audits.features"},
                    {"name": "audits.scoring"},
                    {"name": "audits.recommendations"},
                    {"name": "audits.finalize"},
                ],
            }
    class FakeControl:
        def inspect(self, timeout: float):
            assert timeout == 0.5
            return FakeInspect()
    monkeypatch.setattr("app.health.celery_app.control", FakeControl())
    payload = collect_worker_runtime_metrics(Settings())
    assert payload["status"] == "ok"
    assert payload["topology"]["status"] == "ok"
    assert payload["missing_queues"] == []
    assert payload["workers"]["network@test"]["profile_name"] == "network"
    assert payload["workers"]["heavy@test"]["profile_name"] == "heavy_analysis"
    assert payload["workers"]["cpu@test"]["profile_status"] == "ok"
    assert payload["queue_activity"]["audits.fetch"]["active_tasks"] == 1
    assert payload["queue_activity"]["audits.heavy_analysis"]["active_tasks"] == 1
    assert payload["queue_activity"]["audits.scoring"]["reserved_tasks"] == 1
    assert payload["queue_activity"]["audits.finalize"]["scheduled_tasks"] == 1


def test_collect_worker_runtime_metrics_uses_profile_hostname_when_active_queues_are_missing(monkeypatch: pytest.MonkeyPatch):
    class FakeInspect:
        def stats(self):
            return {
                "site-audit.pipeline@test": {"pid": 1001, "pool": {"max-concurrency": 1}},
                "site-audit.network@test": {"pid": 1002, "pool": {"max-concurrency": 4}},
                "site-audit.heavy_analysis@test": {"pid": 1003, "pool": {"max-concurrency": 2}},
                "site-audit.cpu_ml@test": {"pid": 1004, "pool": {"max-concurrency": 2}},
            }
        def active(self):
            return {"site-audit.network@test": [{"name": "app.process_audit_collect_competitor_page"}]}
        def reserved(self):
            return {}
        def scheduled(self):
            return {}
        def active_queues(self):
            return {}
    class FakeControl:
        def inspect(self, timeout: float):
            assert timeout == 0.5
            return FakeInspect()
    monkeypatch.setattr("app.health.celery_app.control", FakeControl())
    payload = collect_worker_runtime_metrics(Settings())
    assert payload["status"] == "ok"
    assert payload["topology"]["status"] == "ok"
    assert payload["missing_queues"] == []
    assert payload["workers"]["site-audit.network@test"]["queue_source"] == "hostname_fallback"
    assert payload["workers"]["site-audit.network@test"]["profile_name"] == "network"
    assert payload["queue_activity"]["audits.competitor_pages"]["worker_count"] == 1
    assert payload["queue_activity"]["audits.competitor_pages"]["active_tasks"] == 1
    assert payload["queue_activity"]["audits.fetch"]["worker_count"] == 1
    assert payload["queue_activity"]["audits.heavy_analysis"]["worker_count"] == 1


def test_check_celery_worker_health_fails_when_queue_affinity_is_invalid(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.health.collect_worker_runtime_metrics",
        lambda settings: {
            "status": "degraded",
            "online_count": 1,
            "workers": {
                "celery@mixed": {
                    "queues": ["audits.pipeline", "audits.fetch"],
                    "active_tasks": 0,
                    "reserved_tasks": 0,
                    "scheduled_tasks": 0,
                    "pool_max_concurrency": 1,
                    "pid": 123,
                }
            },
            "expected_queues": list(AUDIT_QUEUES),
            "missing_queues": [],
            "queue_activity": {},
            "topology": {
                "status": "error",
                "invalid_workers": ["celery@mixed"],
                "worker_profiles": {
                    "celery@mixed": {
                        "status": "error",
                        "profile_name": None,
                        "reason": "cross_profile_queue_affinity",
                        "queues": ["audits.pipeline", "audits.fetch"],
                        "matched_profiles": ["network", "pipeline"],
                        "unexpected_queues": [],
                    }
                },
                "profiles": {},
                "missing_profiles": ["pipeline", "network", "heavy_analysis", "cpu_ml"],
                "profiles_with_missing_queues": ["pipeline", "network", "heavy_analysis", "cpu_ml"],
                "missing_queues": list(AUDIT_QUEUES),
            },
            "topology_contract": build_worker_topology_contract(),
        },
    )
    health = check_celery_worker_health(Settings())
    assert health.status == "error"
    assert health.details["error"] == "Active workers violate the configured queue-affinity topology."
    assert health.details["topology"]["invalid_workers"] == ["celery@mixed"]
