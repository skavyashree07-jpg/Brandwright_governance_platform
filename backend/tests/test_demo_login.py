import os
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.sql import operators

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-demo-login-tests-32")

from app import api_v1
from app.db import get_db
from app.main import app
from app.models import (
    Brand,
    ContentItem,
    ContentVersion,
    Fact,
    Finding,
    FindingDecision,
    Organisation,
    Rule,
    Term,
    User,
)
from app.config import settings
from app.review.integration import _fact_sources, _rule_sources
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
        def matches_expression(expression):
            clauses = getattr(expression, "clauses", None)
            if clauses is not None:
                checks = [matches_expression(clause) for clause in clauses]
                if expression.operator is operators.or_:
                    return any(checks)
                if expression.operator is operators.and_:
                    return all(checks)
                return False
            if not hasattr(expression, "left") or not hasattr(expression, "right"):
                return False
            key = getattr(expression.left, "key", None)
            current = getattr(record, key, None)
            value = getattr(expression.right, "value", None)
            if expression.operator is operators.is_:
                return current is value
            if expression.operator is operators.is_not:
                return current is not value
            if expression.operator is operators.eq:
                return current == value or str(current) == str(value)
            if expression.operator is operators.gt:
                return current is not None and current > value
            return False

        return all(matches_expression(expression) for expression in self.criteria)

    def first(self):
        return next((row for row in self.database.records.get(self.model, []) if self._matches(row)), None)

    def all(self):
        return [row for row in self.database.records.get(self.model, []) if self._matches(row)]

    def __iter__(self):
        return iter(self.all())


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
    monkeypatch.setattr(settings, "JURY_DEMO_ENABLED", True)
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


def test_admin_brand_management_and_read_only_brand_access(demo_client):
    client, database, users, organisation = demo_client

    def headers(role):
        response = client.post("/api/v1/auth/demo-login", json={"role": role})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    admin_headers = headers("admin")
    created = client.post(
        "/api/v1/brands",
        headers=admin_headers,
        json={
            "name": "Northwind Studio",
            "industry": "Education",
            "website_url": "https://northwind.example",
            "primary_colour": "#244B3D",
        },
    )
    assert created.status_code == 201
    brand = created.json()
    assert brand["name"] == "Northwind Studio"
    assert "logo_file_key" not in brand
    assert "organisation_id" not in brand

    updated = client.patch(
        f"/api/v1/brands/{brand['id']}",
        headers=admin_headers,
        json={"description": "A learning studio", "voice": "Friendly"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "A learning studio"

    creator_headers = headers("creator")
    listed = client.get("/api/v1/brands", headers=creator_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [brand["id"]]
    assert client.get(f"/api/v1/brands/{brand['id']}", headers=headers("reviewer")).status_code == 200
    assert client.post("/api/v1/brands", headers=creator_headers, json={"name": "Not allowed"}).status_code == 403
    assert client.patch(
        f"/api/v1/brands/{brand['id']}",
        headers=creator_headers,
        json={"name": "Not allowed"},
    ).status_code == 403

    other_org = next(row for row in database.records[Organisation] if row.id != organisation.id)
    foreign_brand = Brand(
        id=uuid4(),
        organisation_id=other_org.id,
        name="Private Other Brand",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    database.records.setdefault(Brand, []).append(foreign_brand)
    assert client.get(f"/api/v1/brands/{foreign_brand.id}", headers=admin_headers).status_code == 404

    archived = client.post(f"/api/v1/brands/{brand['id']}/archive", headers=admin_headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.get("/api/v1/brands", headers=admin_headers).json() == []
    assert client.get("/api/v1/brands?include_archived=true", headers=admin_headers).json()[0]["id"] == brand["id"]


def test_brand_schema_rejects_bad_urls_and_colours():
    from pydantic import ValidationError

    from app.schemas import BrandCreateSchema

    with pytest.raises(ValidationError):
        BrandCreateSchema(name="A brand", website_url="javascript:alert(1)")
    with pytest.raises(ValidationError):
        BrandCreateSchema(name="A brand", primary_colour="green")


def test_review_sources_include_shared_and_only_the_selected_brand(demo_client):
    _client, database, _users, organisation = demo_client
    selected_brand_id = uuid4()
    other_brand_id = uuid4()
    database.records[Rule] = [
        Rule(id=uuid4(), organisation_id=organisation.id, brand_id=None, clause_number="S1", text="Shared rule", category="tone", status="approved"),
        Rule(id=uuid4(), organisation_id=organisation.id, brand_id=selected_brand_id, clause_number="B1", text="Selected rule", category="tone", status="approved"),
        Rule(id=uuid4(), organisation_id=organisation.id, brand_id=other_brand_id, clause_number="O1", text="Other rule", category="tone", status="approved"),
    ]
    database.records[Term] = [
        Term(id=uuid4(), organisation_id=organisation.id, brand_id=None, preferred="shared", banned="common"),
        Term(id=uuid4(), organisation_id=organisation.id, brand_id=other_brand_id, preferred="other", banned="different"),
    ]
    database.records[Fact] = [
        Fact(id=uuid4(), organisation_id=organisation.id, brand_id=None, text="Shared fact", status="approved", expires_at=None),
        Fact(id=uuid4(), organisation_id=organisation.id, brand_id=selected_brand_id, text="Selected fact", status="approved", expires_at=None),
        Fact(id=uuid4(), organisation_id=organisation.id, brand_id=other_brand_id, text="Other fact", status="approved", expires_at=None),
    ]

    unbranded_rules = _rule_sources(database, organisation.id)
    unbranded_facts = _fact_sources(database, organisation.id)
    selected_rules = _rule_sources(database, organisation.id, selected_brand_id)
    selected_facts = _fact_sources(database, organisation.id, selected_brand_id)

    assert {source["text"] for source in unbranded_rules} == {"Shared rule", 'Use “shared” instead of “common”.'}
    assert {source["text"] for source in unbranded_facts} == {"Shared fact"}
    assert {source["text"] for source in selected_rules} == {
        "Shared rule",
        "Selected rule",
        'Use “shared” instead of “common”.',
    }
    assert {source["text"] for source in selected_facts} == {"Shared fact", "Selected fact"}


def test_registered_user_login_still_works_when_demo_mode_is_disabled(demo_client, monkeypatch):
    client, database, users, organisation = demo_client
    monkeypatch.setattr(settings, "DEMO_MODE", "false")
    database.query = lambda _model: SimpleNamespace(
        filter=lambda *_criteria: SimpleNamespace(first=lambda: users[1])
    )
    monkeypatch.setattr(api_v1, "verify_password", lambda _password, _hashed: True)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": users[1].email, "password": "valid-password"},
    )

    assert response.status_code == 200
    claims = jwt.decode(response.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["sub"] == str(users[1].id)
    assert claims["org_id"] == str(organisation.id)
    assert claims["role"] == "reviewer"


def test_login_accepts_arbitrary_credentials_only_in_demo_mode(demo_client):
    client, database, users, organisation = demo_client
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "any-password"},
    )

    assert response.status_code == 200
    decoded = jwt.decode(
        response.json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    creator = next(user for user in users if user.role == "creator")
    assert decoded["sub"] == str(creator.id)
    assert decoded["org_id"] == str(organisation.id)
    assert decoded["role"] == "creator"
    assert any(getattr(event, "action", None) == "demo_login" for event in database.added)


def test_login_keeps_password_authentication_when_demo_mode_is_disabled(demo_client, monkeypatch):
    client, database, *_ = demo_client
    monkeypatch.setattr(settings, "DEMO_MODE", "false")
    database.records[User] = []

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "any-password"},
    )

    assert response.status_code == 401


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


def test_jury_demo_login_starts_in_admin_and_marks_the_session(demo_client):
    client, database, users, organisation = demo_client

    response = client.post("/api/v1/auth/jury-demo-login")

    assert response.status_code == 200
    payload = jwt.decode(response.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    admin = next(user for user in users if user.role == "admin")
    assert payload["sub"] == str(admin.id)
    assert payload["org_id"] == str(organisation.id)
    assert payload["role"] == "admin"
    assert payload["session_type"] == "jury_demo"
    assert UUID(payload["jury_session_id"])
    profile = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["jury_demo"] is True
    assert any(getattr(event, "action", None) == "jury_demo_login" for event in database.added)


@pytest.mark.parametrize("role", ["reviewer", "creator", "admin"])
def test_jury_role_switch_preserves_the_session_and_changes_role(demo_client, role):
    client, _database, users, organisation = demo_client
    initial = client.post("/api/v1/auth/jury-demo-login").json()["access_token"]
    initial_claims = jwt.decode(initial, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    response = client.post(
        "/api/v1/auth/jury-switch-role",
        json={"role": role},
        headers={"Authorization": f"Bearer {initial}"},
    )

    assert response.status_code == 200
    next_token = response.json()["access_token"]
    claims = jwt.decode(next_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    target_user = next(user for user in users if user.role == role)
    assert claims["sub"] == str(target_user.id)
    assert claims["org_id"] == str(organisation.id)
    assert claims["role"] == role
    assert claims["jury_session_id"] == initial_claims["jury_session_id"]
    assert claims["exp"] == initial_claims["exp"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {next_token}"})
    assert profile.json()["role"] == role
    assert profile.json()["jury_demo"] is True


def test_jury_demo_endpoint_is_disabled_by_configuration(demo_client, monkeypatch):
    client, *_ = demo_client
    token = client.post("/api/v1/auth/jury-demo-login").json()["access_token"]
    monkeypatch.setattr(settings, "JURY_DEMO_ENABLED", False)
    assert client.post("/api/v1/auth/jury-demo-login").status_code == 404
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 401


def test_non_jury_demo_session_cannot_switch_roles(demo_client):
    client, *_ = demo_client
    token = client.post("/api/v1/auth/demo-login", json={"role": "creator"}).json()["access_token"]
    response = client.post(
        "/api/v1/auth/jury-switch-role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_jury_demo_session_cannot_switch_from_another_organisation(demo_client):
    client, database, _users, _demo_organisation = demo_client
    other_organisation = next(
        org for org in database.records[Organisation]
        if org.name != api_v1.DEMO_ORGANISATION_NAME
    )
    other_admin = User(
        id=uuid4(),
        email="admin@other.example.invalid",
        hashed_password="not-returned",
        role="admin",
        organisation_id=other_organisation.id,
    )
    database.records[User].append(other_admin)
    token = api_v1.create_access_token({
        "sub": str(other_admin.id),
        "org_id": str(other_admin.organisation_id),
        "role": other_admin.role,
        "session_type": "jury_demo",
        "jury_session_id": str(uuid4()),
    })
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 401
    response = client.post(
        "/api/v1/auth/jury-switch-role",
        json={"role": "reviewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_expired_jury_demo_session_cannot_switch_roles(demo_client):
    from datetime import timedelta

    client, _database, users, organisation = demo_client
    admin = next(user for user in users if user.role == "admin")
    token = api_v1.create_access_token({
        "sub": str(admin.id),
        "org_id": str(organisation.id),
        "role": admin.role,
        "session_type": "jury_demo",
        "jury_session_id": str(uuid4()),
    }, expires_delta=timedelta(seconds=-1))
    response = client.post(
        "/api/v1/auth/jury-switch-role",
        json={"role": "reviewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_jury_role_switch_rejects_roles_outside_the_allowlist(demo_client):
    client, *_ = demo_client
    token = client.post("/api/v1/auth/jury-demo-login").json()["access_token"]
    response = client.post(
        "/api/v1/auth/jury-switch-role",
        json={"role": "manager"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


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
