from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.celery_app import AUDIT_QUEUES


@dataclass(frozen=True, slots=True)
class WorkerTopologyProfile:
    name: str
    workload_class: str
    description: str
    recommended_concurrency: int
    queues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "workload_class": self.workload_class,
            "description": self.description,
            "recommended_concurrency": self.recommended_concurrency,
            "queues": list(self.queues),
        }


def _profiles_path() -> Path:
    return Path(__file__).with_name("worker_topology_profiles.json")


def _normalize_queue_names(queue_names: list[str] | tuple[str, ...]) -> list[str]:
    return sorted(dict.fromkeys(str(queue_name) for queue_name in queue_names if queue_name))


@lru_cache(maxsize=1)
def load_worker_topology_profiles() -> tuple[WorkerTopologyProfile, ...]:
    raw_payload = json.loads(_profiles_path().read_text(encoding="utf-8"))
    raw_profiles = raw_payload.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ValueError("worker_topology_profiles.json must define a non-empty profiles list.")

    profiles: list[WorkerTopologyProfile] = []
    seen_names: set[str] = set()
    covered_queues: list[str] = []
    for raw_profile in raw_profiles:
        if not isinstance(raw_profile, dict):
            raise ValueError("worker topology profile entries must be objects.")

        name = str(raw_profile.get("name") or "").strip()
        workload_class = str(raw_profile.get("workload_class") or "").strip()
        description = str(raw_profile.get("description") or "").strip()
        recommended_concurrency = int(raw_profile.get("recommended_concurrency") or 1)
        queues_raw = raw_profile.get("queues")
        if not name or not workload_class or not description:
            raise ValueError("worker topology profiles must define name, workload_class and description.")
        if name in seen_names:
            raise ValueError(f"duplicate worker topology profile name: {name}")
        if not isinstance(queues_raw, list) or not queues_raw:
            raise ValueError(f"worker topology profile '{name}' must define a non-empty queues list.")

        queue_names = tuple(_normalize_queue_names([str(queue_name) for queue_name in queues_raw]))
        profiles.append(
            WorkerTopologyProfile(
                name=name,
                workload_class=workload_class,
                description=description,
                recommended_concurrency=max(recommended_concurrency, 1),
                queues=queue_names,
            )
        )
        seen_names.add(name)
        covered_queues.extend(queue_names)

    duplicate_queues = sorted({queue_name for queue_name in covered_queues if covered_queues.count(queue_name) > 1})
    if duplicate_queues:
        raise ValueError(
            "worker topology queue affinity must assign each queue to exactly one profile: "
            + ", ".join(duplicate_queues)
        )

    expected_queues = sorted(AUDIT_QUEUES)
    missing_queues = sorted(set(expected_queues) - set(covered_queues))
    unknown_queues = sorted(set(covered_queues) - set(expected_queues))
    if missing_queues or unknown_queues:
        raise ValueError(
            "worker topology profiles must cover the Celery audit queues exactly once. "
            f"missing={missing_queues}, unknown={unknown_queues}"
        )

    return tuple(profiles)


@lru_cache(maxsize=1)
def get_profile_name_by_queue() -> dict[str, str]:
    return {
        queue_name: profile.name
        for profile in load_worker_topology_profiles()
        for queue_name in profile.queues
    }


def build_worker_topology_contract() -> dict[str, Any]:
    profiles = load_worker_topology_profiles()
    return {
        "profiles": [profile.to_dict() for profile in profiles],
        "expected_queues": sorted(AUDIT_QUEUES),
    }


def evaluate_worker_topology(worker_queues: dict[str, list[str] | tuple[str, ...]]) -> dict[str, Any]:
    profiles = load_worker_topology_profiles()
    profile_name_by_queue = get_profile_name_by_queue()
    profile_coverage = {
        profile.name: {
            "workload_class": profile.workload_class,
            "description": profile.description,
            "recommended_concurrency": profile.recommended_concurrency,
            "queues": list(profile.queues),
            "covered_queues": [],
            "missing_queues": list(profile.queues),
            "workers": [],
            "worker_count": 0,
        }
        for profile in profiles
    }
    worker_profiles: dict[str, dict[str, Any]] = {}
    invalid_workers: list[str] = []

    for worker_name, raw_queue_names in sorted(worker_queues.items()):
        normalized_queue_names = _normalize_queue_names(list(raw_queue_names))
        queue_profiles = sorted(
            {
                profile_name_by_queue.get(queue_name)
                for queue_name in normalized_queue_names
                if queue_name in profile_name_by_queue
            }
        )
        unexpected_queues = sorted(
            queue_name
            for queue_name in normalized_queue_names
            if queue_name not in profile_name_by_queue
        )
        matched_profile_name = queue_profiles[0] if len(queue_profiles) == 1 and not unexpected_queues else None

        if not normalized_queue_names:
            worker_profiles[worker_name] = {
                "status": "error",
                "profile_name": None,
                "reason": "worker_without_active_queues",
                "queues": [],
                "matched_profiles": [],
                "unexpected_queues": [],
            }
            invalid_workers.append(worker_name)
            continue

        if unexpected_queues:
            worker_profiles[worker_name] = {
                "status": "error",
                "profile_name": None,
                "reason": "unexpected_queue_affinity",
                "queues": normalized_queue_names,
                "matched_profiles": queue_profiles,
                "unexpected_queues": unexpected_queues,
            }
            invalid_workers.append(worker_name)
            continue

        if len(queue_profiles) != 1 or matched_profile_name is None:
            worker_profiles[worker_name] = {
                "status": "error",
                "profile_name": None,
                "reason": "cross_profile_queue_affinity",
                "queues": normalized_queue_names,
                "matched_profiles": queue_profiles,
                "unexpected_queues": [],
            }
            invalid_workers.append(worker_name)
            continue

        coverage_entry = profile_coverage[matched_profile_name]
        coverage_entry["workers"].append(worker_name)
        coverage_entry["covered_queues"] = _normalize_queue_names(
            list(coverage_entry["covered_queues"]) + normalized_queue_names
        )
        coverage_entry["missing_queues"] = sorted(
            set(coverage_entry["queues"]) - set(coverage_entry["covered_queues"])
        )
        worker_profiles[worker_name] = {
            "status": "ok",
            "profile_name": matched_profile_name,
            "reason": "queue_affinity_valid",
            "queues": normalized_queue_names,
            "matched_profiles": [matched_profile_name],
            "unexpected_queues": [],
        }

    missing_profiles: list[str] = []
    profiles_with_missing_queues: list[str] = []
    missing_queues: list[str] = []
    for profile_name, coverage_entry in profile_coverage.items():
        coverage_entry["workers"] = sorted(set(str(worker_name) for worker_name in coverage_entry["workers"]))
        coverage_entry["worker_count"] = len(coverage_entry["workers"])
        if not coverage_entry["workers"]:
            missing_profiles.append(profile_name)
        if coverage_entry["missing_queues"]:
            profiles_with_missing_queues.append(profile_name)
            missing_queues.extend(str(queue_name) for queue_name in coverage_entry["missing_queues"])

    if not worker_profiles:
        status = "warning"
    elif invalid_workers or profiles_with_missing_queues:
        status = "error"
    else:
        status = "ok"

    return {
        "status": status,
        "profiles": profile_coverage,
        "worker_profiles": worker_profiles,
        "invalid_workers": sorted(invalid_workers),
        "missing_profiles": sorted(missing_profiles),
        "profiles_with_missing_queues": sorted(profiles_with_missing_queues),
        "missing_queues": _normalize_queue_names(missing_queues),
    }
