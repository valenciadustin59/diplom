from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import Audit  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "audits" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("audits")}
    required_columns = {
        "top_n": "ALTER TABLE audits ADD COLUMN top_n INTEGER NOT NULL DEFAULT 10",
        "updated_at": "ALTER TABLE audits ADD COLUMN updated_at DATETIME",
        "extracted_text": "ALTER TABLE audits ADD COLUMN extracted_text TEXT",
        "target_html": "ALTER TABLE audits ADD COLUMN target_html TEXT",
        "features": "ALTER TABLE audits ADD COLUMN features JSON",
        "score": "ALTER TABLE audits ADD COLUMN score FLOAT",
        "score_breakdown": "ALTER TABLE audits ADD COLUMN score_breakdown JSON",
        "competitor_results": "ALTER TABLE audits ADD COLUMN competitor_results JSON",
        "comparison_summary": "ALTER TABLE audits ADD COLUMN comparison_summary JSON",
        "recommendations": "ALTER TABLE audits ADD COLUMN recommendations JSON",
        "target_fetch_status": "ALTER TABLE audits ADD COLUMN target_fetch_status TEXT",
        "target_fetch_method": "ALTER TABLE audits ADD COLUMN target_fetch_method TEXT",
        "target_fetch_error_code": "ALTER TABLE audits ADD COLUMN target_fetch_error_code TEXT",
        "target_fetch_error_message": "ALTER TABLE audits ADD COLUMN target_fetch_error_message TEXT",
        "failure_context": "ALTER TABLE audits ADD COLUMN failure_context JSON",
        "warnings": "ALTER TABLE audits ADD COLUMN warnings JSON",
        "error_message": "ALTER TABLE audits ADD COLUMN error_message TEXT",
    }

    missing_statements = [
        statement
        for column_name, statement in required_columns.items()
        if column_name not in existing_columns
    ]
    if not missing_statements:
        return

    with engine.begin() as connection:
        for statement in missing_statements:
            connection.execute(text(statement))
