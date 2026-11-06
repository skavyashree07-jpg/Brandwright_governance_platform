from app.review.llm_review import build_ai_findings
from app.review.privacy import redact_sensitive, prepare_external_payload
from app.review.claims import verify_claims

class Inventing:
    def review(self,*args): return [{"source_id":"fake","start":0,"end":2}]

def test_fake_source_discarded():
    assert build_ai_findings("hi","intent",[{"id":"valid"}],Inventing())==[]

def test_redaction():
    r=redact_sensitive("mail a@b.com Project Falcon",["Project Falcon"])
    assert "a@b.com" not in r.text and "Project Falcon" not in r.text

def test_local_only():
    assert not prepare_external_payload("secret",local_only=True)["allowed"]

def test_claim_cannot_verify():
    fs,usage=verify_claims("It lasts 3x longer.",[])
    assert fs and fs[0].status=="cannot_verify" and usage==[]


def test_privacy_masks_identifiers_and_preserves_offsets():
    from app.review.privacy import prepare_external_payload
    text = "Contact kavya@example.com, PAN ABCDE1234F, Aadhaar 1234 5678 9012, IP 192.168.1.10, phone 9876543210."
    result = prepare_external_payload(text, local_only=False)
    assert result["allowed"] is True
    assert len(result["text"]) == len(text)
    assert "kavya@example.com" not in result["text"]
    assert "ABCDE1234F" not in result["text"]
    assert "1234 5678 9012" not in result["text"]
    assert "192.168.1.10" not in result["text"]
    assert "9876543210" not in result["text"]


def test_claude_client_uses_forced_structured_tool_and_returns_findings():
    from types import SimpleNamespace
    from app.review.llm_review import ClaudeLLMClient

    class FakeMessages:
        def create(self, **kwargs):
            assert kwargs["tool_choice"] == {"type": "tool", "name": "submit_findings"}
            return SimpleNamespace(content=[SimpleNamespace(
                type="tool_use", name="submit_findings",
                input={"findings": [{"source_id": "r1", "start": 0, "end": 4,
                    "category": "tone", "severity": "low", "explanation": "Tone mismatch"}]})])

    fake = SimpleNamespace(messages=FakeMessages())
    client = ClaudeLLMClient("fake-key", "fake-model", client=fake)
    findings = client.review("Hey!", "Announce", [{"id": "r1", "text": "Use formal tone"}])
    assert findings[0]["source_id"] == "r1"


def test_no_retrieved_sources_means_no_model_call():
    from app.review.pipeline import review_text

    class NeverCall:
        service_name = "must-not-run"
        def review(self, *args, **kwargs):
            raise AssertionError("model must not be called without retrieved sources")

    result = review_text("Some plain content", "Introduce content", [], [],
                         local_only=False, llm_client=NeverCall())
    assert result["ai_services_used"] == []
    assert result["ai_usage"] == []
    assert result["ai_skipped_reason"] == "No approved sources were retrieved."


def test_intent_and_retrieved_source_are_redacted_before_external_call():
    from app.review.pipeline import review_text

    class InspectClient:
        service_name = "test-external"
        def review(self, text, intent, sources):
            assert "kavya@example.com" not in text
            assert "kavya@example.com" not in intent
            assert all("kavya@example.com" not in str(source) for source in sources)
            return []

    result = review_text(
        "Share the update with kavya@example.com", "Email kavya@example.com about the launch",
        [{"id": "r1", "text": "Email launch policy", "status": "approved"}], [],
        local_only=False, llm_client=InspectClient(),
    )
    assert result["privacy"]["unredacted_external_calls"] == 0
    assert result["ai_usage"][0]["redacted"] is True


def test_confidential_and_expired_sources_are_filtered_before_ranking():
    from app.review.retrieval import InMemoryRetriever
    sources = [
        {"id": "secret", "text": "brand voice launch", "confidential": True},
        {"id": "expired", "text": "brand voice launch", "expires_at": "2000-01-01T00:00:00Z"},
        {"id": "approved", "text": "brand voice launch", "status": "approved"},
    ]
    found = InMemoryRetriever(sources).retrieve("brand voice launch")
    assert [source["id"] for source in found] == ["approved"]


def test_intent_lock_suppresses_suggestion_without_dropping_finding():
    class Suggesting:
        def review(self, *args):
            return [{"source_id": "r1", "start": 0, "end": 7, "category": "messaging",
                     "severity": "medium", "explanation": "Possible mismatch",
                     "suggestion": "Visit our store today."}]

    findings = build_ai_findings("Battery launch", "Announce battery performance",
        [{"id": "r1", "text": "Keep battery messaging factual"}], Suggesting())
    assert len(findings) == 1
    assert findings[0].suggestion is None
    assert findings[0].trace["intent_lock"] == "rejected"


def test_model_failure_is_logged_without_losing_deterministic_findings():
    from app.review.pipeline import review_text

    class BrokenClient:
        service_name = "test-external"
        model = "test-model"
        def review(self, *args):
            raise TimeoutError("do not persist raw provider error text")

    result = review_text(
        "This is cheap.", "Describe the product", 
        [{"id": "r1", "text": "Avoid cheap terminology", "type": "banned_term",
          "config": {"term": "cheap"}}], [], local_only=False, llm_client=BrokenClient())
    assert any(f.category == "terminology" for f in result["findings"])
    assert result["ai_usage"][0]["error"] == "TimeoutError"
    assert result["ai_usage"][0]["blocked"] is True
    assert "do not persist" not in str(result["ai_usage"])
