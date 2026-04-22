from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AuditFailureContextRead(BaseModel):
    stage: str
    code: str | None = None
    message: str
    details: dict[str, object] | None = None


class AuditCreate(BaseModel):
    query: str = Field(min_length=1)
    target_url: HttpUrl
    top_n: int = Field(default=10, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    query: str
    target_url: str
    top_n: int
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    extracted_text: str | None = None
    feature_schema_version: str | None = None
    features: dict[str, float | int] | None = None
    score: float | None = None
    score_breakdown: dict[str, object] | None = None
    competitor_results: list[dict[str, object]] | None = None
    comparison_summary: dict[str, float | int] | None = None
    recommendations: list[dict[str, str]] | None = None
    target_fetch_status: str | None = None
    target_fetch_method: str | None = None
    target_fetch_error_code: str | None = None
    target_fetch_error_message: str | None = None
    failure_context: AuditFailureContextRead | None = None
    warnings: list[str] | None = None
    error_message: str | None = None


class AuditResultsRead(BaseModel):
    audit_id: str
    status: str
    score: float | None = None
    extracted_text: str | None = None
    feature_schema_version: str | None = None
    target_snapshot_summary: dict[str, object] | None = None
    features: dict[str, float | int] | None = None
    score_breakdown: dict[str, object] | None = None
    competitor_results: list[dict[str, object]] | None = None
    comparison_summary: dict[str, float | int] | None = None
    target_fetch_status: str | None = None
    target_fetch_method: str | None = None
    target_fetch_error_code: str | None = None
    target_fetch_error_message: str | None = None
    failure_context: AuditFailureContextRead | None = None
    warnings: list[str] | None = None
    error_message: str | None = None


class AuditRecommendationsRead(BaseModel):
    audit_id: str
    status: str
    recommendations: list[dict[str, str]]
    failure_context: AuditFailureContextRead | None = None
    error_message: str | None = None


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    audit_id: str
    processing_version: int | None = None
    stage: str
    event: str
    duration_ms: float | None = None
    details: dict[str, object] | None = None
    created_at: datetime


class AuditEventTimelineRead(BaseModel):
    audit_id: str
    processing_version: int | None = None
    events: list[AuditEventRead]


class AuditTimelineStageDiagnosticsRead(BaseModel):
    stage: str
    dispatch_count: int
    started_count: int
    completed_count: int
    failed_count: int
    aborted_count: int
    terminal_count: int
    total_duration_ms: float | None = None
    average_duration_ms: float | None = None
    max_duration_ms: float | None = None
    critical_path_mode: str
    critical_path_duration_ms: float | None = None
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    latest_event: str | None = None


class AuditTimelineCriticalPathStageRead(BaseModel):
    stage: str
    contribution_duration_ms: float | None = None
    mode: str
    terminal_count: int


class AuditTimelineFanOutRead(BaseModel):
    stage: str
    dispatch_count: int
    started_count: int
    terminal_count: int
    in_flight_count: int
    total_duration_ms: float | None = None
    average_duration_ms: float | None = None
    max_duration_ms: float | None = None
    critical_path_duration_ms: float | None = None


class AuditTimelineDiagnosticsRead(BaseModel):
    audit_id: str
    processing_version: int | None = None
    status: str
    event_count: int
    dispatch_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_duration_ms: float | None = None
    terminal_stage: str | None = None
    terminal_event: str | None = None
    critical_path_duration_ms: float | None = None
    critical_path_stages: list[AuditTimelineCriticalPathStageRead]
    stage_breakdown: list[AuditTimelineStageDiagnosticsRead]
    fan_out: AuditTimelineFanOutRead | None = None
