from app.trust.evaluator import calculate_metrics
from app.review.intent_lock import preserves_intent
from app.insights.guideline_drafting import draft_rule_clarification

def test_metrics():
    m=calculate_metrics(["tone","claim"],["tone","visual"])
    assert m["precision"]==0.5 and m["recall"]==0.5

def test_intent_lock_rejects_number_change():
    assert not preserves_intent("announce battery performance","Battery lasts 40% longer",
                                "Announce improved battery performance")

def test_guideline_draft_requires_owner():
    d=draft_rule_clarification({"id":"r1","text":"Use friendly tone"},
        [{"id":"d1","action":"dismiss","reason":"unclear for formal announcements"}])
    assert d["status"]=="draft" and d["requires_owner_approval"] and d["motivating_decisions"]==["d1"]


def test_scorecard_category_metrics_and_traces():
    from app.trust.evaluator import evaluate_dataset
    samples = [{
        "id": "s1",
        "expected_issues": ["tone", "claim"],
    }]
    result = evaluate_dataset(samples, lambda _: {
        "findings": [{"category": "tone"}, {"category": "visual"}],
        "trace": {"retrieved_source_ids": ["r1"]},
    })
    assert result["true_positive"] == 1
    assert result["false_positive"] == 1
    assert result["false_negative"] == 1
    assert result["per_category"]["tone"]["recall"] == 1.0
    assert result["per_category"]["claim"]["recall"] == 0.0
    assert result["traces"][0]["missed_expected"] == ["claim"]
    assert result["traces"][0]["pipeline_trace"]["retrieved_source_ids"] == ["r1"]


def test_scorecard_matches_specific_rule_ids_and_reports_f1():
    from app.trust.evaluator import calculate_metrics
    metrics = calculate_metrics(
        [{"category": "tone", "rule_id": "r-1"}],
        [{"category": "tone", "source": {"id": "r-1"}}],
    )
    assert metrics["true_positive"] == 1
    assert metrics["f1"] == 1.0


def test_guideline_draft_carries_decision_evidence():
    draft = draft_rule_clarification(
        {"id": "r1", "text": "Use a friendly tone"},
        [{"id": "d1", "action": "edit", "reason": "Formal notices need a neutral tone",
          "finding_id": "f1", "quote": "Hey!!!"}],
    )
    assert draft["evidence"][0]["finding_id"] == "f1"
    assert draft["motivating_decisions"] == ["d1"]
    assert draft["requires_owner_approval"] is True


def test_guideline_draft_rejects_missing_rule_id_or_text():
    import pytest
    with pytest.raises(ValueError):
        draft_rule_clarification({"text": "No id"}, [])
    with pytest.raises(ValueError):
        draft_rule_clarification({"id": "r1", "text": " "}, [])


def test_guideline_health_ranks_dismissed_rules():
    from app.insights.guideline_drafting import calculate_guideline_health
    decisions = [
        {"id": "d1", "rule_id": "r1", "action": "dismiss"},
        {"id": "d2", "rule_id": "r1", "action": "dismiss"},
        {"id": "d3", "rule_id": "r1", "action": "edit"},
        {"id": "d4", "rule_id": "r2", "action": "accept"},
    ]
    result = calculate_guideline_health(decisions, min_decisions=3)
    assert result["items"][0]["rule_id"] == "r1"
    assert result["items"][0]["dismiss_rate"] == 0.6667
    assert result["items"][0]["override_rate"] == 0.3333
    assert result["items"][0]["false_positive_flag"] is True
    assert result["items"][1]["sample_sufficient"] is False
