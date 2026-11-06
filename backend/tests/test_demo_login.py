import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from redis.exceptions import ConnectionError as RedisConnectionError

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-demo-login-tests-32")

from app import api_v1
from app.db import get_db
from app.main import app
from app.models import (
    ContentItem,
    ContentVersion,
    Finding,
    FindingDecision,
    Organisation,
    User,
)
from app.config import settings
import seed


class FakeQuery:
    def __init__(self, database, model):
        self.database = database
        self.model = model
        self.criteria = []
        self.filters = {}

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def filter_by(self, **filters):
        self.filters.update(filters)
        return self

    def join(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def _matches(self, record):
        if any(getattr(record, key, None) != value for key, value in self.filters.items()):
            return False
        for expression in self.criteria:
            if not hasattr(expression, "left") or not hasattr(expression, "right"):
                return False
            key = getattr(expression.left, "key", None)
            value = getattr(expression.right, "value", None)
            if str(getattr(record, key, None)) != str(value):
                return False
        return True

    def first(self):
        return next((row for row in self.database.records.get(self.model, []) if self._matches(row)), None)

    def all(self):
        return [row for row in self.database.records.get(self.model, []) if self._matches(row)]


class FakeDatabase:
    def __init__(self, records=None):
        self.records = records or {}
        self.added = []

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, record):
        self.added.append(record)
        self.records.setdefault(type(record), []).append(record)

    def flush(self):
        for record in self.added:
            if hasattr(record, "id") and getattr(record, "id", None) is None:
                record.id = uuid4()

    def commit(self):
        self.flush()

    def refresh(self, _record):
        return None

    def close(self):
        return None


class OfflineRedis:
    def eval(self, *_args):
        raise RedisConnectionError()


class SharedFakeRedis:
    def __init__(self):
        self.windows = {}

    def eval(self, _script, _key_count, key, now, window, limit, member):
        attempts = [
            stamp for stamp, _entry in self.windows.get(key, [])
            if float(now) - stamp < int(window)
        ]
        if len(attempts) >= int(limit):
            self.windows[key] = [(stamp, entry) for stamp, entry in self.windows[key] if float(now) - stamp < int(window)]
            return 0
        attempts.append(float(now))
        self.windows[key] = [(stamp, entry) for stamp, entry in self.windows.get(key, []) if float(now) - stamp < int(window)]
        self.windows[key].append((float(now), member))
        return 1


@pytest.fixture
def demo_client(monkeypatch):
    organisation = Organisation(id=uuid4(), name=api_v1.DEMO_ORGANISATION_NAME)
    users = [
        User(
            id=uuid4(),
            email=f"{role}@demo.brandwright.app",
            hashed_password="not-returned",
            role=role,
            organisation_id=organisation.id,
        )
        for role in ("creator", "reviewer", "admin")
    ]
    other_organisation = Organisation(id=uuid4(), name="Another Demo Organisation")
    other_creator = User(
        id=uuid4(),
        email="other@example.invalid",
        hashed_password="not-returned",
        role="creator",
        organisation_id=other_organisation.id,
    )
    contents = [
        ContentItem(
            id=uuid4(),
            organisation_id=organisation.id,
            creator_id=users[0].id,
            title="Demo organisation content",
            current_version_no=1,
            status="draft",
        ),
        ContentItem(
            id=uuid4(),
            organisation_id=other_organisation.id,
            creator_id=other_creator.id,
            title="Other organisation content",
            current_version_no=1,
            status="draft",
        ),
    ]
    database = FakeDatabase({
        Organisation: [organisation, other_organisation],
        User: [*users, other_creator],
        ContentItem: contents,
    })

    def override_db():
        yield database

    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key-for-demo-login-tests-32")
    monkeypatch.setattr(settings, "DEMO_MODE", "true")
    monkeypatch.setattr(api_v1, "_demo_login_attempts", {})
    monkeypatch.setattr(api_v1, "_demo_login_redis", OfflineRedis())
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, database, users, organisation
    app.dependency_overrides.pop(get_db, None)


def test_demo_login_is_hidden_when_demo_mode_is_disabled(demo_client, monkeypatch):
    client, *_ = demo_client
    monkeypatch.setattr(settings, "DEMO_MODE", "false")
    assert client.post("/api/v1/auth/demo-login", json={"role": "creator"}).status_code == 404


@pytest.mark.parametrize("role", ["creator", "reviewer", "admin"])
def test_demo_login_issues_the_normal_role_scoped_token(demo_client, role):
    client, database, users, organisation = demo_client
    response = client.post("/api/v1/auth/demo-login", json={"role": role})
    assert response.status_code == 200
    payload = response.json()
    decoded = jwt.decode(payload["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    user = next(row for row in users if row.role == role)
    assert payload["token_type"] == "bearer"
    assert decoded["sub"] == str(user.id)
    assert decoded["org_id"] == str(organisation.id)
    assert decoded["role"] == role
    assert "hashed_password" not in payload
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["role"] == role
    assert profile.json()["organisation_id"] == str(organisation.id)
    assert any(getattr(event, "action", None) == "demo_login" for event in database.added)


def test_demo_login_rejects_unknown_role_and_unseeded_users(demo_client):
    client, database, *_ = demo_client
    assert client.post("/api/v1/auth/demo-login", json={"role": "manager"}).status_code == 422

    organisation = Organisation(id=uuid4(), name=api_v1.DEMO_ORGANISATION_NAME)
    empty_db = FakeDatabase({Organisation: [organisation], User: []})

    def override_empty_db():
        yield empty_db

    original_override = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = override_empty_db
    response = client.post("/api/v1/auth/demo-login", json={"role": "creator"})
    def restore_db():
        yield database
    app.dependency_overrides[get_db] = original_override or restore_db
    assert response.status_code == 503


def test_demo_login_rate_limit_is_ten_requests_per_minute(demo_client):
    client, *_ = demo_client
    for _ in range(api_v1.DEMO_LOGIN_LIMIT):
        assert client.post("/api/v1/auth/demo-login", json={"role": "creator"}).status_code == 200
    response = client.post("/api/v1/auth/demo-login", json={"role": "creator"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_redis_rate_limit_is_shared_and_enforces_the_same_threshold(monkeypatch):
    monkeypatch.setattr(api_v1, "_demo_login_redis", SharedFakeRedis())
    monkeypatch.setattr(api_v1, "_demo_login_attempts", {})
    for _ in range(api_v1.DEMO_LOGIN_LIMIT):
        api_v1._enforce_demo_login_limit("192.0.2.12")
    with pytest.raises(HTTPException) as error:
        api_v1._enforce_demo_login_limit("192.0.2.12")
    assert getattr(error.value, "status_code", None) == 429


def test_demo_roles_keep_existing_permission_boundaries(demo_client):
    client, *_ = demo_client
    creator_token = client.post("/api/v1/auth/demo-login", json={"role": "creator"}).json()["access_token"]
    reviewer_token = client.post("/api/v1/auth/demo-login", json={"role": "reviewer"}).json()["access_token"]
    creator_response = client.get(
        "/api/v1/trust/scorecard",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    reviewer_response = client.patch(
        f"/api/v1/kb/rules/{uuid4()}",
        json={"text": "No changes"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert creator_response.status_code == 403
    assert reviewer_response.status_code == 403


def test_demo_session_is_scoped_to_its_organisation(demo_client):
    client, *_ = demo_client
    token = client.post("/api/v1/auth/demo-login", json={"role": "creator"}).json()["access_token"]
    response = client.get("/api/v1/content", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Demo organisation content"]


def test_review_uses_sync_fallback_when_redis_is_unavailable(monkeypatch):
    database = FakeDatabase()
    user = SimpleNamespace(id=uuid4(), organisation_id=uuid4())
    content = SimpleNamespace(id=uuid4())
    version = SimpleNamespace(
        id=uuid4(),
        status="queued",
        review_job_id=str(uuid4()),
        review_error=None,
        review_job_status=None,
        review_stage=None,
        source_file_key=None,
        body="A local draft",
    )
    def redis_unavailable(*_args):
        raise RedisConnectionError()

    monkeypatch.setattr(api_v1, "enqueue_review", redis_unavailable)
    monkeypatch.setattr(api_v1, "_do_review", lambda *_args: {
        "findings": [{"id": "sample-finding"}],
        "engine_status": "ok",
        "ai_services_used": [],
    })

    result = api_v1._schedule_review(database, user, content, version)

    assert result["status"] == "completed"
    assert version.review_job_status == "completed"
    assert [event.status for event in database.records[api_v1.ReviewEvent]] == ["queued", "running", "completed"]


class SeedFakeDatabase(FakeDatabase):
    def flush(self):
        for record in self.added:
            if hasattr(record, "id") and getattr(record, "id", None) is None:
                record.id = uuid4()


def test_seed_demo_data_is_idempotent(monkeypatch):
    class Embedder:
        def embed(self, _text):
            return None

    monkeypatch.setattr(seed, "create_embedder", Embedder)
    database = SeedFakeDatabase()
    seed.seed_demo_data(database)
    seeded_password_hashes = {
        user.email: user.hashed_password for user in database.records[User]
    }
    seed.seed_demo_data(database)

    assert len(database.records[Organisation]) == 1
    assert len(database.records[User]) == 3
    assert len(database.records[ContentItem]) == 4
    assert len(database.records[ContentVersion]) == 4
    assert len(database.records[Finding]) == 3
    assert len(database.records[FindingDecision]) == 1
    assert {user.email: user.hashed_password for user in database.records[User]} == seeded_password_hashes
