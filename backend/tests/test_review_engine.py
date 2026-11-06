from uuid import uuid4
from datetime import datetime, timedelta, timezone

import pytest

from app.review.llm_review import MockLLMClient
from app.review.pipeline import review_text
from app.review.rule_engine import run_rule_engine


@pytest.mark.parametrize(
    ("rule_type", "config", "text", "expected_category"),
    [
        ("banned_term", {"term": "cheap", "replacement": "affordable"}, "A cheap option", "terminology"),
        ("preferred_term", {"preferred": "battery pack", "variants": ["battery"]}, "A battery included", "terminology"),
        ("required_disclaimer", {"phrase": "Terms apply"}, "Offer ends today", "messaging"),
        ("superlative", {"terms": ["safest"]}, "The safest option", "claim"),
    ],
)
def test_deterministic_rule_types(rule_type, config, text, expected_category):
    source_id = str(uuid4())
    rule = {
        "id": source_id,
        "type": rule_type,
        "text": "Approved demonstration rule",
        "category": expected_category,
        "config": config,
        "status": "approved",
    }

    findings = run_rule_engine(text, [rule], content_id="content-1", version_no=2)

    assert findings
    assert findings[0].category == expected_category
    assert findings[0].source["id"] == source_id
    assert findings[0].content_id == "content-1"
    assert findings[0].version_no == 2


def test_channel_specific_rule_is_not_applied_to_other_channel():
    rule = {
        "id": str(uuid4()),
        "type": "banned_term",
        "text": "Avoid this term",
        "category": "terminology",
        "channels": ["email"],
        "config": {"term": "cheap"},
    }

    assert not run_rule_engine("cheap plans", [rule], channel="Website")
    assert run_rule_engine("cheap plans", [rule], channel="Email")


def test_unsupported_claim_routes_to_human_without_source():
    result = review_text(
        "Our product is the safest on the market.",
        "Promote our product",
        [],
        [],
        content_id="content-2",
        local_only=True,
    )

    claim = next(item for item in result["findings"] if item.category == "claim")
    assert claim.status == "cannot_verify"
    assert claim.source is None


def test_expired_fact_cannot_support_a_claim():
    result = review_text(
        "Our product is the safest on the market.",
        "Promote our product",
        [],
        [{
            "id": str(uuid4()),
            "text": "Our product is the safest on the market.",
            "status": "approved",
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }],
        content_id="content-expired-fact",
    )

    claim = next(item for item in result["findings"] if item.category == "claim")
    assert claim.status == "cannot_verify"
    assert not result["fact_usage"]


def test_retrieval_ai_finding_must_cite_retrieved_source():
    source_id = str(uuid4())
    rule = {
        "id": source_id,
        "source_type": "rule",
        "text": "Use clear product language",
        "category": "messaging",
        "status": "approved",
        "match_text": "super exciting",
        "suggestion": "Promote this product clearly",
    }

    result = review_text(
        "Our product is super exciting.",
        "Promote our product",
        [rule],
        [],
        content_id="content-3",
        llm_client=MockLLMClient(),
    )

    ai_finding = next(item for item in result["findings"] if item.check_type == "retrieval_ai")
    assert ai_finding.source["id"] == source_id
    assert ai_finding.suggestion["intent_preserved"] is True
