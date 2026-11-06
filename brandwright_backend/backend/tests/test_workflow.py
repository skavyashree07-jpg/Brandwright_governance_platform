def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_content_state_machine(client, seed_data):
    headers = {"Authorization": f"Bearer {seed_data['creator_token']}"}
    
    res = client.post("/api/v1/content", json={
        "title": "Launch Deck",
        "body": "Welcome to our platform.",
        "intent": "Introduce brand"
    }, headers=headers)
    assert res.status_code == 200
    content_id = res.json()["id"]

    res_submit = client.post(f"/api/v1/content/{content_id}/submit", headers=headers)
    assert res_submit.status_code == 200
    assert res_submit.json()["status"] == "in_review"

    rev_headers = {"Authorization": f"Bearer {seed_data['reviewer_token']}"}
    res_approve = client.post(f"/api/v1/content/{content_id}/approve", headers=rev_headers)
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "approved"

    res_illegal = client.post(f"/api/v1/content/{content_id}/submit", headers=headers)
    assert res_illegal.status_code == 409
