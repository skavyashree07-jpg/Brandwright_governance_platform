def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_text_review_is_persisted_and_retrievable(client):
    payload = {
        "content": "Our battery is the safest. Use battery pack.",
        "intent": "Announce the battery product",
        "content_id": "campaign-1",
        "rules": [{"id": "rule-1", "text": "Avoid safest", "type": "superlative",
                   "config": {"terms": ["safest"]}}],
        "facts": [], "local_only": True
    }
    created = client.post("/api/engine/reviews", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "completed"
    assert len(body["findings"]) >= 1
    fetched = client.get(f"/api/engine/reviews/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["content_id"] == "campaign-1"


def test_upload_text_then_review_document(client):
    upload = client.post("/api/engine/documents", files={"file": ("draft.txt", b"Hello brand world", "text/plain")})
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    reviewed = client.post(f"/api/engine/documents/{document_id}/review", json={
        "intent": "Introduce the brand", "content_id": "uploaded-1", "local_only": True
    })
    assert reviewed.status_code == 201, reviewed.text
    assert reviewed.json()["document_id"] == document_id


def test_unsupported_upload_is_rejected(client):
    response = client.post("/api/engine/documents", files={"file": ("draft.exe", b"x", "application/octet-stream")})
    assert response.status_code == 415


def test_trust_run_and_history(client):
    response = client.post("/api/engine/trust/run", json={"samples": [{
        "id": "sample-1", "content": "Our product is the safest.", "intent": "Product launch",
        "rules": [{"id": "r1", "text": "Avoid safest", "type": "superlative",
                   "config": {"terms": ["safest"]}}], "expected_issues": ["superlative"]
    }]})
    assert response.status_code == 201, response.text
    assert response.json()["run_id"]
    history = client.get("/api/engine/trust/scorecard")
    assert history.status_code == 200
    assert history.json()["latest"] is not None


def test_guideline_clarification_is_saved_as_draft(client):
    response = client.post("/api/engine/guidelines/clarifications", json={
        "rule": {"id": "r-22", "text": "Use a clear, friendly tone."},
        "decisions": [{"id": "d1", "action": "dismiss", "reason": "Rule too broad"}]
    })
    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert response.json()["requires_owner_approval"] is True
    assert response.json()["evidence"][0]["reason"] == "Rule too broad"
    assert client.get("/api/engine/guidelines/clarifications").json()["items"][0]["evidence"]


def test_guideline_parser_endpoint_returns_drafts(client):
    response = client.post("/api/engine/guidelines/parse", json={
        "text": "1.1 Brand voice\nUse a friendly tone on social channels."
    })
    assert response.status_code == 200
    assert response.json()["rules"][0]["status"] == "draft"
    assert response.json()["requires_owner_approval"] is True


def test_image_review_endpoint(client):
    from io import BytesIO
    from PIL import Image
    image = Image.new("RGB", (24, 24), "white")
    buf = BytesIO(); image.save(buf, format="PNG")
    response = client.post("/api/engine/images/review",
        files={"file": ("creative.png", buf.getvalue(), "image/png")},
        data={"alt_text": "", "foreground": "#777777", "background": "#FFFFFF"})
    assert response.status_code == 200, response.text
    assert response.json()["width"] == 24
    assert response.json()["findings"]


def test_trust_run_loads_bundled_fictional_eval_set(client):
    response = client.post("/api/engine/trust/run")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["dataset_source"] == "bundled_fictional_demo"
    assert body["sample_count"] == 5
    assert body["benchmark_warning"]
    assert body["macro_f1"] >= 0
    assert body["traces"]


def test_guideline_health_uses_recorded_human_decisions(client):
    review = client.post("/api/engine/reviews", json={
        "content": "This product is cheap.", "intent": "Describe product",
        "rules": [{"id": "r-health", "text": "Avoid cheap", "type": "banned_term",
                   "config": {"term": "cheap"}}], "facts": [], "local_only": True
    })
    assert review.status_code == 201, review.text
    finding_id = review.json()["findings"][0]["id"]
    for index in range(3):
        decision = client.post(f"/api/engine/findings/{finding_id}/decision", json={
            "rule_id": "r-health", "action": "dismiss", "reason": f"Reason {index}",
            "actor_role": "reviewer"
        })
        assert decision.status_code == 201, decision.text
    health = client.get("/api/engine/insights/guideline-health?min_decisions=3")
    assert health.status_code == 200, health.text
    assert health.json()["items"][0]["rule_id"] == "r-health"
    assert health.json()["items"][0]["false_positive_flag"] is True


def test_dismissal_requires_reason(client):
    review = client.post("/api/engine/reviews", json={
        "content": "This product is cheap.", "intent": "Describe product",
        "rules": [{"id": "r-reason", "text": "Avoid cheap", "type": "banned_term",
                   "config": {"term": "cheap"}}], "facts": [], "local_only": True
    })
    finding_id = review.json()["findings"][0]["id"]
    response = client.post(f"/api/engine/findings/{finding_id}/decision", json={
        "rule_id": "r-reason", "action": "dismiss", "reason": " "
    })
    assert response.status_code == 422


def test_ai_usage_log_is_available_without_storing_content(client):
    response = client.post("/api/engine/reviews", json={
        "content": "Email kavya@example.com for details.", "intent": "Share contact details", 
        "rules": [{"id": "contact-rule", "text": "Contact email policy", "type": "guideline",
                   "match_text": "kavya@example.com"}], "facts": [], "local_only": False
    })
    assert response.status_code == 201, response.text
    usage = client.get(f"/api/engine/reviews/{response.json()['id']}/ai-usage")
    assert usage.status_code == 200, usage.text
    assert usage.json()["items"]
    row = usage.json()["items"][0]
    assert row["redacted"] is True
    assert row["redaction_counts"]["email"] >= 1
    assert "kavya@example.com" not in str(row)


def test_guideline_draft_can_use_saved_reviewer_decisions(client):
    review = client.post("/api/engine/reviews", json={
        "content": "This product is cheap.", "intent": "Describe product",
        "rules": [{"id": "r-draft", "text": "Avoid cheap", "type": "banned_term",
                   "config": {"term": "cheap"}}], "facts": [], "local_only": True
    })
    finding_id = review.json()["findings"][0]["id"]
    decision = client.post(f"/api/engine/findings/{finding_id}/decision", json={
        "rule_id": "r-draft", "action": "dismiss", "reason": "Context differs for formal offers"
    })
    assert decision.status_code == 201
    draft = client.post("/api/engine/guidelines/clarifications", json={
        "rule": {"id": "r-draft", "text": "Avoid cheap"}, "decisions": []
    })
    assert draft.status_code == 201, draft.text
    assert draft.json()["motivating_decisions"] == [decision.json()["id"]]
    assert draft.json()["evidence"][0]["reason"] == "Context differs for formal offers"
