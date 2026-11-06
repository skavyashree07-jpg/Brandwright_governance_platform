import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.models import Organisation, User
from app.security import get_password_hash, create_access_token

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def client(db_session):
    def _get_test_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def seed_data(db_session):
    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    creator = User(email="creator@test.com", hashed_password=get_password_hash("password"), role="creator", organisation_id=org.id)
    reviewer = User(email="reviewer@test.com", hashed_password=get_password_hash("password"), role="reviewer", organisation_id=org.id)
    admin = User(email="admin@test.com", hashed_password=get_password_hash("password"), role="admin", organisation_id=org.id)
    
    db_session.add_all([creator, reviewer, admin])
    db_session.commit()

    return {
        "org": org,
        "creator": creator,
        "reviewer": reviewer,
        "admin": admin,
        "creator_token": create_access_token({"sub": str(creator.id), "org_id": str(org.id), "role": "creator"}),
        "reviewer_token": create_access_token({"sub": str(reviewer.id), "org_id": str(org.id), "role": "reviewer"}),
        "admin_token": create_access_token({"sub": str(admin.id), "org_id": str(org.id), "role": "admin"})
    }
