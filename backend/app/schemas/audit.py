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
