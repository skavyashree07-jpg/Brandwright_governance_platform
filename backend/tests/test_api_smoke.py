import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-valid-for-deployment-32")

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_integrated_api_contract():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    paths = app.openapi()["paths"]
    assert "/api/v1/content/upload" in paths
    assert "/api/v1/content/{content_id}/review" in paths
    assert "/api/v1/reviews/{review_id}/events" in paths
    assert "/api/v1/trust/run" in paths
