import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config import settings
from app.db import Base, get_db
from app.models import ContentItem, ContentVersion, Organisation, ReviewEvent, User
from app.review.progress import validate_review_transition
from app.review.pipeline import review_text
from app.security import create_access_token
from app.review.llm_review import MockLLMClient
from app.workers import should_retry_review


def test_review_state_machine_allows_queue_progress_and_completion():
    validate_review_transition(None, "queued")
    validate_review_transition("queued", "running")
    validate_review_transition("running", "completed")
    validate_review_transition("running", "failed")


def test_content_workflow_accepts_human_review_transitions_and_rejects_unsafe_role_access():
    from fastapi import HTTPException

    from app.workflow import transition_content_status

    content = SimpleNamespace(id=uuid4(), status="draft")
    db = SimpleNamespace(add=lambda *args, **kwargs: None, flush=lambda: None)
    transition_content_status(db, content, "submitted", "user-1", "org-1", user_role="creator")

    content.status = "submitted"
    transition_content_status(db, content, "queued", "user-1", "org-1", user_role="reviewer")

    try:
        content.status = "queued"
        transition_content_status(db, content, "approved", "user-1", "org-1", user_role="creator")
        assert False, "Creator should not be allowed to approve content."
    except HTTPException:
        pass


def test_review_state_machine_rejects_resuming_terminal_job():
    with pytest.raises(ValueError, match="Illegal review status transition"):
        validate_review_transition("completed", "running")

    with pytest.raises(ValueError, match="Illegal review status transition"):
        validate_review_transition("failed", "completed")


def test_retryable_network_failure_retries_but_exhausted_or_bad_input_does_not():
    assert should_retry_review(TimeoutError("provider timeout"), retries_left=3)
    assert should_retry_review(ConnectionError("provider unavailable"), retries_left=2)
    assert should_retry_review(TimeoutError("provider timeout"), retries_left=1)
    assert not should_retry_review(TimeoutError("provider timeout"), retries_left=0)
    assert not should_retry_review(ValueError("invalid review payload"), retries_left=3)


def test_worker_requeues_transient_failure_and_marks_exhausted_failure(monkeypatch):
    import app.workers as workers

    version_id, user_id = uuid4(), uuid4()
    organisation_id = uuid4()
    version = SimpleNamespace(
        id=version_id,
        content_id=uuid4(),
        review_job_status="queued",
        review_stage="queued",
        review_error=None,
        source_file_key=None,
        body="Review body",
        intent="Review intent",
        status="queued",
    )
    user = SimpleNamespace(id=user_id, organisation_id=organisation_id)
    content = SimpleNamespace(id=version.content_id, organisation_id=organisation_id)
    events = []

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *_conditions):
            return self

        def join(self, *_entities):
            return self

        def first(self):
            return {
                ContentVersion: version,
                User: user,
                ContentItem: content,
            }[self.model]

    class FakeSession:
        def query(self, model):
            return FakeQuery(model)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    def fake_record(db, row, org_id, status, stage, message, **kwargs):
        row.review_job_status = status
        row.review_stage = stage
        events.append(status)

    monkeypatch.setattr(workers, "SessionLocal", FakeSession)
    monkeypatch.setattr(workers, "record_review_event", fake_record)

    def fail_review(*args, **kwargs):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(workers, "run_and_persist_review", fail_review)
    monkeypatch.setattr(workers, "get_current_job", lambda: SimpleNamespace(retries_left=2))

    with pytest.raises(TimeoutError):
        workers.process_review_job(str(version_id), str(user_id))

    assert version.status == "queued"
    assert version.review_job_status == "running"
    assert events == ["running", "running", "running"]

    version.review_job_status = "queued"
    events.clear()
    monkeypatch.setattr(workers, "get_current_job", lambda: SimpleNamespace(retries_left=0))
    result = workers.process_review_job(str(version_id), str(user_id))
    assert result["status"] == "failed"
    assert version.status == "failed"
    assert version.review_job_status == "failed"


def test_rq_queue_sets_retry_backoff_and_timeout(monkeypatch):
    import app.workers as workers

    captured = {}

    class QueueStub:
        def enqueue(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return "job"

    monkeypatch.setattr(workers, "review_queue", QueueStub())
    monkeypatch.setattr(workers.settings, "REVIEW_JOB_TIMEOUT_SECONDS", 123)

    assert workers.enqueue_review(uuid4(), uuid4(), str(uuid4())) == "job"
    retry = captured["kwargs"]["retry"]
    assert retry.max == 3
    assert retry.intervals == [5, 15, 30]
    assert captured["kwargs"]["job_timeout"] == 123
    assert captured["kwargs"]["on_failure"] is workers.handle_review_failure


def test_pipeline_emits_progress_after_each_review_stage():
    source_id = str(uuid4())
    source = {
        "id": source_id,
        "source_type": "rule",
        "text": "Avoid overexcited language.",
        "category": "messaging",
        "status": "approved",
        "channels": ["all"],
        "match_text": "super exciting",
        "suggestion": "Promote the product clearly.",
    }
    stages = []

    class Retriever:
        def retrieve(self, text, intent="", channel=None, limit=8):
            return [source]

    result = review_text(
        "Our product is super exciting.",
        "Promote the product",
        [source],
        [],
        retriever=Retriever(),
        llm_client=MockLLMClient(),
        progress_callback=lambda stage, status, findings: stages.append(
            (stage, status, len(findings))
        ),
    )

    assert [stage for stage, _, _ in stages] == [
        "deterministic_checks", "claim_verification", "ai_review", "ai_review",
    ]
    assert stages[-1] == ("ai_review", "completed", 1)
    assert result["findings"]


@pytest.fixture
def progress_database(monkeypatch):
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run SSE authentication and tenant isolation tests.")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    import app.api_v1 as api_module

    monkeypatch.setattr(api_module, "SessionLocal", factory)
    settings.SECRET_KEY = "test-only-secret-that-is-long-enough-123"
    yield factory
    engine.dispose()


def test_sse_requires_auth_and_is_organisation_scoped(progress_database):
    from app.main import app

    db = progress_database()
    org_a = Organisation(name=f"sse-a-{uuid4()}")
    org_b = Organisation(name=f"sse-b-{uuid4()}")
    db.add_all([org_a, org_b])
    db.flush()
    user_a = User(
        email=f"sse-a-{uuid4()}@example.test",
        hashed_password="unused",
        role="reviewer",
        organisation_id=org_a.id,
    )
    user_b = User(
        email=f"sse-b-{uuid4()}@example.test",
        hashed_password="unused",
        role="reviewer",
        organisation_id=org_b.id,
    )
    db.add_all([user_a, user_b])
    db.flush()
    content = ContentItem(
        organisation_id=org_a.id,
        creator_id=user_a.id,
        title="SSE test",
        current_version_no=1,
        status="draft",
    )
    db.add(content)
    db.flush()
    job_id = str(uuid4())
    version = ContentVersion(
        content_id=content.id,
        version_no=1,
        body="Progress test body",
        intent="Test streaming",
        status="reviewed",
        review_job_id=job_id,
        review_job_status="completed",
        review_stage="completed",
    )
    db.add(version)
    db.flush()
    db.add(ReviewEvent(
        organisation_id=org_a.id,
        content_version_id=version.id,
        status="completed",
        stage="completed",
        message="Review completed.",
        findings=[],
        metadata_json={},
    ))
    token_a = create_access_token({"sub": str(user_a.id), "org_id": str(org_a.id), "role": user_a.role})
    token_b = create_access_token({"sub": str(user_b.id), "org_id": str(org_b.id), "role": user_b.role})
    db.commit()
    db.close()

    def override_db():
        session = progress_database()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.get(f"/api/v1/reviews/{job_id}/events").status_code == 401
            response = client.get(
                f"/api/v1/reviews/{job_id}/events",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 200
            assert "event: review" in response.text
            assert '"status": "completed"' in response.text
            assert client.get(
                f"/api/v1/reviews/{job_id}/events",
                headers={"Authorization": f"Bearer {token_b}"},
            ).status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        cleanup = progress_database()
        cleanup.query(ReviewEvent).filter(ReviewEvent.organisation_id.in_([org_a.id, org_b.id])).delete(
            synchronize_session=False
        )
        cleanup.query(ContentVersion).filter(ContentVersion.id == version.id).delete(synchronize_session=False)
        cleanup.query(ContentItem).filter(ContentItem.id == content.id).delete(synchronize_session=False)
        cleanup.query(User).filter(User.id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
        cleanup.query(Organisation).filter(Organisation.id.in_([org_a.id, org_b.id])).delete(
            synchronize_session=False
        )
        cleanup.commit()
        cleanup.close()
