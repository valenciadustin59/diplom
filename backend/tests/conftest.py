from collections.abc import Generator
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.api.dependencies import get_db_session
from app.db import Base
from app.main import app
from app.tasks import process_audit
@pytest.fixture()
def queued_audit_ids(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    ids: list[str] = []
    def fake_enqueue(audit_id: str):
        ids.append(audit_id)
        return None
    monkeypatch.setattr('app.api.routes.audits.enqueue_audit_processing', fake_enqueue)
    return ids
@pytest.fixture()
def client(tmp_path: Path, queued_audit_ids: list[str]) -> Generator[TestClient, None, None]:
    db_path = tmp_path / 'test_audit.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db_session] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
@pytest.fixture()
def integration_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / 'test_audit_integration.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()
    def inline_enqueue(audit_id: str) -> None:
        process_audit.run(audit_id)
    monkeypatch.setattr('app.api.routes.audits.enqueue_audit_processing', inline_enqueue)
    app.dependency_overrides[get_db_session] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()