from app.review_tasks import redact_sensitive_data

def test_redact_sensitive_data():
    sample = "Contact support at test@example.com or call 555-123-4567 or (555) 987-6543."
    redacted = redact_sensitive_data(sample)
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "555-123-4567" not in redacted
    assert "test@example.com" not in redacted

def test_fact_drift_and_guideline_health(client, seed_data):
    admin_headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    
    fact_res = client.post("/api/v1/kb/facts", json={
        "text": "Brandwright latency is under 150ms.",
        "owner": "Engineering"
    }, headers=admin_headers)
    assert fact_res.status_code == 200
    fact_id = fact_res.json()["id"]

    update_res = client.patch(f"/api/v1/kb/facts/{fact_id}", json={
        "text": "Brandwright latency is under 100ms."
    }, headers=admin_headers)
    assert update_res.status_code == 200
    assert update_res.json()["version"] == 2

    health_res = client.get("/api/v1/insights/guideline-health", headers=admin_headers)
    assert health_res.status_code == 200
    assert isinstance(health_res.json(), list)
