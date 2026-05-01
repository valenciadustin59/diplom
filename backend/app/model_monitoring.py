from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import ceil, floor
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Audit

DEFAULT_WINDOW_DAYS = 30
LOW_SCORE_THRESHOLD = 50.0
HIGH_SCORE_THRESHOLD = 80.0
MAX_WINDOW_DAYS = 365
MIN_WINDOW_DAYS = 1


@dataclass(frozen=True)
class ModelIdentity:
    artifact_version: str | None
    model_schema_version: str | None
    dataset_version: str | None
    model_type: str | None
    source: str | None
    artifact_family: str | None
    feature_count: int | None

    @property
    def key(self) -> str:
        return "|".join(
            [
                self.artifact_version or "unknown-artifact",
                self.model_schema_version or "unknown-schema",
                self.dataset_version or "unknown-dataset",
                self.model_type or "unknown-model",
                self.source or "unknown-source",
            ]
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "artifact_version": self.artifact_version,
            "model_schema_version": self.model_schema_version,
            "dataset_version": self.dataset_version,
            "model_type": self.model_type,
            "source": self.source,
            "artifact_family": self.artifact_family,
            "feature_count": self.feature_count,
        }


@dataclass
class ModelUsageAccumulator:
    identity: ModelIdentity
    audit_count: int = 0
    status_counts: Counter[str] = field(default_factory=Counter)
    warning_count: int = 0
    warning_message_count: int = 0
    failure_count: int = 0
    scores: list[float] = field(default_factory=list)
    competitors_found: int = 0
    competitors_analyzed: int = 0
    competitors_failed: int = 0
    competitor_sample_size: int = 0
    last_audit_at: datetime | None = None

    def add(self, audit: Audit) -> None:
        self.audit_count += 1
        self.status_counts.update([str(audit.status or "unknown")])
        self.last_audit_at = _max_datetime(self.last_audit_at, audit.created_at)

        if _audit_has_warning(audit):
            self.warning_count += 1
        self.warning_message_count += _warning_message_count(audit.warnings)
        if _audit_has_failure(audit):
            self.failure_count += 1

        score = _safe_float(audit.score)
        if score is not None:
            self.scores.append(score)

        coverage = extract_competitor_coverage(audit)
        self.competitors_found += coverage["found"]
        self.competitors_analyzed += coverage["analyzed"]
        self.competitors_failed += coverage["failed"]
        self.competitor_sample_size += 1

    def as_payload(self, *, active_identity: ModelIdentity | None = None) -> dict[str, Any]:
        return {
            **self.identity.as_payload(),
            "is_active_model": _same_identity(self.identity, active_identity),
            "audit_count": self.audit_count,
            "status_counts": dict(sorted(self.status_counts.items())),
            "warning_count": self.warning_count,
            "warning_message_count": self.warning_message_count,
            "failure_count": self.failure_count,
            "score_distribution": build_score_distribution(self.scores),
            "competitor_coverage": build_competitor_coverage(
                found=self.competitors_found,
                analyzed=self.competitors_analyzed,
                failed=self.competitors_failed,
                sample_size=self.competitor_sample_size,
            ),
            "last_audit_at": _isoformat_utc(self.last_audit_at),
        }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _as_db_datetime(value: datetime) -> datetime:
    return _as_utc(value).replace(tzinfo=None)


def _isoformat_utc(value: datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value is not None else None


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number and number not in (float("inf"), float("-inf")) else None
    return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _safe_positive_int(value: Any) -> int | None:
    number = _safe_int(value)
    return number if number is not None and number >= 0 else None


def _safe_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _max_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return right if _as_utc(right) > _as_utc(left) else left


def _warning_message_count(warnings: Any) -> int:
    return len([item for item in warnings if isinstance(item, str) and item.strip()]) if isinstance(warnings, list) else 0


def _audit_has_warning(audit: Audit) -> bool:
    return audit.status == "completed_with_warnings" or _warning_message_count(audit.warnings) > 0


def _audit_has_failure(audit: Audit) -> bool:
    return audit.status == "failed" or audit.failure_context is not None or bool(audit.error_message)


def _round_metric(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _percentile(sorted_values: list[float], quantile: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * quantile
    lower_index = floor(position)
    upper_index = ceil(position)
    if lower_index == upper_index:
        return sorted_values[int(position)]
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * (position - lower_index)


def build_score_distribution(scores: list[float]) -> dict[str, Any]:
    values = sorted(score for score in scores if _safe_float(score) is not None)
    sample_size = len(values)
    average = sum(values) / sample_size if sample_size else None
    return {
        "sample_size": sample_size,
        "average": _round_metric(average),
        "min": _round_metric(values[0]) if values else None,
        "max": _round_metric(values[-1]) if values else None,
        "p25": _round_metric(_percentile(values, 0.25)),
        "p50": _round_metric(_percentile(values, 0.5)),
        "p75": _round_metric(_percentile(values, 0.75)),
        "low_score_count": sum(1 for score in values if score < LOW_SCORE_THRESHOLD),
        "high_score_count": sum(1 for score in values if score >= HIGH_SCORE_THRESHOLD),
        "low_score_threshold": LOW_SCORE_THRESHOLD,
        "high_score_threshold": HIGH_SCORE_THRESHOLD,
    }


def build_competitor_coverage(*, found: int, analyzed: int, failed: int, sample_size: int) -> dict[str, Any]:
    return {
        "sample_size": sample_size,
        "total_found": found,
        "total_analyzed": analyzed,
        "total_failed": failed,
        "average_found": _round_metric(found / sample_size) if sample_size else None,
        "average_analyzed": _round_metric(analyzed / sample_size) if sample_size else None,
        "average_failed": _round_metric(failed / sample_size) if sample_size else None,
        "coverage_ratio": _round_metric(analyzed / found) if found else None,
    }


def _extract_model_info(audit: Audit) -> dict[str, Any] | None:
    score_breakdown = audit.score_breakdown if isinstance(audit.score_breakdown, dict) else {}
    model_info = score_breakdown.get("model_info")
    if not isinstance(model_info, dict) or not model_info:
        return None
    return model_info


def extract_model_identity(model_info: dict[str, Any]) -> ModelIdentity:
    return ModelIdentity(
        artifact_version=_safe_str(model_info.get("artifact_version")),
        model_schema_version=_safe_str(model_info.get("model_schema_version")),
        dataset_version=_safe_str(model_info.get("dataset_version")),
        model_type=_safe_str(model_info.get("model_type")),
        source=_safe_str(model_info.get("source")),
        artifact_family=_safe_str(model_info.get("artifact_family")),
        feature_count=_safe_positive_int(model_info.get("feature_count")),
    )


def extract_active_model_identity(model_status: dict[str, Any] | None) -> ModelIdentity | None:
    if not isinstance(model_status, dict):
        return None
    model = model_status.get("model") if isinstance(model_status.get("model"), dict) else {}
    dataset = model_status.get("dataset") if isinstance(model_status.get("dataset"), dict) else {}
    identity = ModelIdentity(
        artifact_version=_safe_str(model.get("artifact_version")),
        model_schema_version=_safe_str(model.get("model_schema_version")),
        dataset_version=_safe_str(dataset.get("dataset_version")) or _safe_str(model.get("dataset_version")),
        model_type=_safe_str(model.get("model_type")),
        source=_safe_str(model.get("source")),
        artifact_family=_safe_str(model.get("artifact_family")),
        feature_count=_safe_positive_int(model.get("feature_count")),
    )
    return identity if any(value is not None for value in identity.as_payload().values() if value != identity.key) else None


def _same_identity(left: ModelIdentity, right: ModelIdentity | None) -> bool:
    if right is None:
        return False
    comparable_fields = [
        "artifact_version",
        "model_schema_version",
        "dataset_version",
        "model_type",
    ]
    return all(
        getattr(left, field_name) == getattr(right, field_name)
        for field_name in comparable_fields
        if getattr(right, field_name) is not None
    )


def extract_competitor_coverage(audit: Audit) -> dict[str, int]:
    summary = audit.comparison_summary if isinstance(audit.comparison_summary, dict) else {}
    found = _safe_positive_int(summary.get("competitors_found"))
    analyzed = _safe_positive_int(summary.get("competitors_analyzed") or summary.get("competitors_count"))
    failed = _safe_positive_int(summary.get("competitors_failed"))

    competitor_results = audit.competitor_results if isinstance(audit.competitor_results, list) else []
    if found is None:
        found = len([item for item in competitor_results if isinstance(item, dict)])
    if analyzed is None:
        analyzed = len(
            [
                item
                for item in competitor_results
                if isinstance(item, dict)
                and _safe_float(item.get("score")) is not None
                and (item.get("features") is None or isinstance(item.get("features"), dict))
            ]
        )
    if failed is None:
        failed = max(found - analyzed, 0)

    return {"found": found, "analyzed": analyzed, "failed": failed}


def _build_recent_audits_query(window_start: datetime, limit: int | None = None) -> Select[tuple[Audit]]:
    statement = select(Audit).where(Audit.created_at >= _as_db_datetime(window_start)).order_by(Audit.created_at.desc())
    return statement.limit(limit) if limit is not None else statement


def _build_overall_status(*, total_audits: int, audits_with_model_info: int, warning_count: int, failure_count: int) -> str:
    if total_audits == 0 or audits_with_model_info == 0:
        return "empty"
    if failure_count > 0:
        return "error"
    if warning_count > 0:
        return "warning"
    return "ok"


def build_model_monitoring_payload(
    db: Session,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: datetime | None = None,
    limit: int | None = None,
    active_model_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_window_days = min(max(window_days, MIN_WINDOW_DAYS), MAX_WINDOW_DAYS)
    checked_at = _as_utc(now or _utc_now())
    window_start = checked_at - timedelta(days=normalized_window_days)
    audits = list(db.execute(_build_recent_audits_query(window_start, limit=limit)).scalars())
    active_identity = extract_active_model_identity(active_model_status)

    status_counts: Counter[str] = Counter()
    warning_count = 0
    warning_message_count = 0
    failure_count = 0
    legacy_or_unknown_count = 0
    active_scores: list[float] = []
    active_competitors = {"found": 0, "analyzed": 0, "failed": 0, "sample_size": 0}
    usage: dict[str, ModelUsageAccumulator] = {}

    for audit in audits:
        status_counts.update([str(audit.status or "unknown")])
        if _audit_has_warning(audit):
            warning_count += 1
        warning_message_count += _warning_message_count(audit.warnings)
        if _audit_has_failure(audit):
            failure_count += 1

        model_info = _extract_model_info(audit)
        if model_info is None:
            legacy_or_unknown_count += 1
            continue

        identity = extract_model_identity(model_info)
        accumulator = usage.setdefault(identity.key, ModelUsageAccumulator(identity=identity))
        accumulator.add(audit)

        if _same_identity(identity, active_identity):
            score = _safe_float(audit.score)
            if score is not None:
                active_scores.append(score)
            coverage = extract_competitor_coverage(audit)
            active_competitors["found"] += coverage["found"]
            active_competitors["analyzed"] += coverage["analyzed"]
            active_competitors["failed"] += coverage["failed"]
            active_competitors["sample_size"] += 1

    usage_rows = sorted(
        (accumulator.as_payload(active_identity=active_identity) for accumulator in usage.values()),
        key=lambda row: (row["is_active_model"] is not True, -int(row["audit_count"]), str(row["artifact_version"] or "")),
    )
    audits_with_model_info = sum(int(row["audit_count"]) for row in usage_rows)

    return {
        "status": _build_overall_status(
            total_audits=len(audits),
            audits_with_model_info=audits_with_model_info,
            warning_count=warning_count,
            failure_count=failure_count,
        ),
        "checked_at": checked_at.isoformat(),
        "window_days": normalized_window_days,
        "window_start": window_start.isoformat(),
        "window_end": checked_at.isoformat(),
        "total_audits": len(audits),
        "audits_with_model_info": audits_with_model_info,
        "legacy_or_unknown_count": legacy_or_unknown_count,
        "status_counts": dict(sorted(status_counts.items())),
        "warning_count": warning_count,
        "warning_message_count": warning_message_count,
        "failure_count": failure_count,
        "active_model": active_identity.as_payload() if active_identity else None,
        "score_distribution": build_score_distribution(active_scores),
        "competitor_coverage": build_competitor_coverage(
            found=active_competitors["found"],
            analyzed=active_competitors["analyzed"],
            failed=active_competitors["failed"],
            sample_size=active_competitors["sample_size"],
        ),
        "model_usage": usage_rows,
    }
