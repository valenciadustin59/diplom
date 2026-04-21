from __future__ import annotations
from collections.abc import Mapping
QUEUED = "queued"
PROCESSING = "processing"
COMPLETED = "completed"
COMPLETED_WITH_WARNINGS = "completed_with_warnings"
FAILED = "failed"
TERMINAL_STATUSES = frozenset({COMPLETED, COMPLETED_WITH_WARNINGS, FAILED})
_ALLOWED_TRANSITIONS: Mapping[str, frozenset[str]] = {
    QUEUED: frozenset({PROCESSING, FAILED}),
    PROCESSING: frozenset({COMPLETED, COMPLETED_WITH_WARNINGS, FAILED}),
    COMPLETED: frozenset({PROCESSING}),
    COMPLETED_WITH_WARNINGS: frozenset({PROCESSING}),
    FAILED: frozenset({PROCESSING}),
}
def transition_status(current_status: str, next_status: str) -> str:
    if current_status == next_status:
        return next_status
    allowed_statuses = _ALLOWED_TRANSITIONS.get(current_status)
    if allowed_statuses is None or next_status not in allowed_statuses:
        raise ValueError(
            f"Invalid audit status transition: {current_status!r} -> {next_status!r}"
        )
    return next_status
