from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    top_n: Mapped[int] = mapped_column(nullable=False, default=10)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    processing_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orchestration_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor_processing_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    features: Mapped[dict[str, float | int] | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    competitor_results: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    comparison_summary: Mapped[dict[str, float | int] | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    target_fetch_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_fetch_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_fetch_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_fetch_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_context: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditCompetitor(Base):
    __tablename__ = "audit_competitors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    audit_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    serp_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    serp_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fetch_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fetch_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fetch_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetch_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    features: Mapped[dict[str, float | int] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    processing_version: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
