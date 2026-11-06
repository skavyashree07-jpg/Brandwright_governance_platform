"""Evidence-linked guideline clarification drafting. Drafts are never approvals."""
from __future__ import annotations
from typing import Any

_RELEVANT_ACTIONS = {"dismiss", "edit", "approve", "reject", "flag", "escalate"}


def _decision_evidence(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence = []
    for decision in decisions:
        action = str(decision.get("action", "")).strip().lower()
        if action not in _RELEVANT_ACTIONS:
            continue
        item = {
            "decision_id": decision.get("id"),
            "action": action,
            "reason": str(decision.get("reason") or "").strip(),
        }
        # Keep only evidence actually supplied by the review record.
        for field in ("finding_id", "content_id", "quote", "edited_text", "reviewer_role", "created_at"):
            if decision.get(field) is not None:
                item[field] = decision[field]
        if item["reason"] or item.get("quote") or item.get("edited_text"):
            evidence.append(item)
    return evidence


def draft_rule_clarification(rule: dict[str, Any], decisions: list[dict[str, Any]], llm_client=None) -> dict[str, Any]:
    """Create a traceable clarification proposal; owner approval is always required."""
    rule_id = rule.get("id") or rule.get("rule_id")
    current_text = str(rule.get("text") or "").strip()
    if not rule_id:
        raise ValueError("rule must include id or rule_id")
    if not current_text:
        raise ValueError("rule text is required")

    evidence = _decision_evidence(decisions)
    if llm_client:
        drafted = llm_client.draft_clarification(rule=rule, examples=evidence)
    else:
        reasons = [x["reason"] for x in evidence if x.get("reason")]
        context = "; ".join(reasons[:3]) or "Reviewers need a clearer scope and examples."
        drafted = (
            f"{current_text}\n\nClarification draft: define the intended scope, explain when this rule "
            f"applies, and include compliant and non-compliant examples.\n\n"
            f"Evidence to consider: {context}"
        )
    if not isinstance(drafted, str) or not drafted.strip():
        raise ValueError("clarification generator returned an empty draft")

    return {
        "rule_id": str(rule_id),
        "current_text": current_text,
        "drafted_text": drafted.strip(),
        "motivating_decisions": [x["decision_id"] for x in evidence if x.get("decision_id")],
        "evidence": evidence,
        "status": "draft",
        "requires_owner_approval": True,
        "approval_note": "This is a proposal only; it does not change the active guideline.",
    }


def calculate_guideline_health(decisions: list[dict[str, Any]], min_decisions: int = 3) -> dict[str, Any]:
    """Aggregate reviewer outcomes per rule and rank rules by likely ambiguity.

    Dismiss and edit rates are transparent signals, not proof that a rule is wrong.
    A false-positive flag is raised only after the minimum sample count is reached.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        rule_id = str(decision.get("rule_id") or "").strip()
        action = str(decision.get("action") or "").strip().lower()
        if rule_id and action in {"accept", "edit", "dismiss"}:
            grouped.setdefault(rule_id, []).append(decision)

    items = []
    for rule_id, rows in grouped.items():
        total = len(rows)
        dismissed = sum(row.get("action") == "dismiss" for row in rows)
        edited = sum(row.get("action") == "edit" for row in rows)
        accepted = sum(row.get("action") == "accept" for row in rows)
        dismiss_rate = dismissed / total if total else 0.0
        override_rate = edited / total if total else 0.0
        # Dismissals are a stronger ambiguity signal than edits.
        clarity_risk = 0.6 * dismiss_rate + 0.4 * override_rate
        items.append({
            "rule_id": rule_id,
            "decision_count": total,
            "accept_count": accepted,
            "edit_count": edited,
            "dismiss_count": dismissed,
            "dismiss_rate": round(dismiss_rate, 4),
            "override_rate": round(override_rate, 4),
            "clarity_risk": round(clarity_risk, 4),
            "false_positive_flag": total >= min_decisions and dismiss_rate >= 0.4,
            "sample_sufficient": total >= min_decisions,
            "motivating_decision_ids": [row.get("id") for row in rows if row.get("id")],
        })
    items.sort(key=lambda item: (item["clarity_risk"], item["decision_count"]), reverse=True)
    return {"items": items, "min_decisions": min_decisions,
            "note": "Dismissal and edit rates are review signals; a guideline owner must assess context."}
