from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AIUsageLog,
    Asset,
    ContentItem,
    ContentVersion,
    Fact,
    FactUsage,
    Finding,
    FindingDecision,
    Rule,
    Term,
    User,
)
from app.review.pipeline import review_text
from app.review.pgvector_retrieval import PgVectorRetriever


def _rule_sources(db: Session, organisation_id: UUID) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for rule in db.query(Rule).filter(
        Rule.organisation_id == organisation_id,
        Rule.status == "approved",
    ):
        sources.append({
            "id": str(rule.id),
            "source_type": "rule",
            "text": rule.text,
            "category": rule.category,
            "channels": rule.channels or ["all"],
            "status": rule.status,
            "sensitivity": rule.sensitivity,
            "type": rule.type,
            "config": rule.config or {},
        })

    for term in db.query(Term).filter(Term.organisation_id == organisation_id):
        sources.append({
            "id": str(term.id),
            "source_type": "rule",
            "text": term.notes or f"Use “{term.preferred}” instead of “{term.banned}”.",
            "category": "terminology",
            "channels": ["all"],
            "status": "approved",
            "type": "banned_term",
            "config": {"term": term.banned, "replacement": term.preferred},
        })
    return sources


def _fact_sources(db: Session, organisation_id: UUID) -> list[dict[str, Any]]:
    return [
        {
            "id": str(fact.id),
            "source_type": "fact",
            "text": fact.text,
            "status": fact.status,
            "expires_at": fact.expires_at.isoformat() if fact.expires_at else None,
            "sensitivity": "normal",
        }
        for fact in db.query(Fact).filter(
            Fact.organisation_id == organisation_id,
            Fact.status == "approved",
            (Fact.expires_at.is_(None)) | (Fact.expires_at > datetime.utcnow()),
        )
    ]


def _source_is_valid(
    db: Session,
    organisation_id: UUID,
    source_type: str | None,
    source_id: UUID | None,
) -> tuple[bool, str]:
    if source_id is None:
        return False, ""
    if source_type == "rule":
        rule = db.query(Rule).filter(
            Rule.id == source_id,
            Rule.organisation_id == organisation_id,
            Rule.status == "approved",
        ).first()
        if rule:
            return True, rule.text
        term = db.query(Term).filter(
            Term.id == source_id,
            Term.organisation_id == organisation_id,
        ).first()
        if term:
            return True, term.notes or f"Use “{term.preferred}” instead of “{term.banned}”."
    elif source_type == "fact":
        fact = db.query(Fact).filter(
            Fact.id == source_id,
            Fact.organisation_id == organisation_id,
            Fact.status == "approved",
            (Fact.expires_at.is_(None)) | (Fact.expires_at > datetime.utcnow()),
        ).first()
        if fact:
            return True, fact.text
    elif source_type == "asset":
        asset = db.query(Asset).filter(
            Asset.id == source_id,
            Asset.organisation_id == organisation_id,
        ).first()
        if asset:
            return True, asset.name
    return False, ""


def serialize_finding(db: Session, row: Finding, version: ContentVersion, organisation_id: UUID) -> dict[str, Any]:
    source_type = row.source_type
    source_id = row.source_id
    valid_source, clause_text = _source_is_valid(db, organisation_id, source_type, source_id)
    status = row.status
    if status == "violation" and not valid_source:
        status = "cannot_verify"

    latest_decision = (
        db.query(FindingDecision)
        .filter(FindingDecision.finding_id == row.id)
        .order_by(FindingDecision.created_at.desc())
        .first()
    )
    decision = None
    if latest_decision:
        decision = {
            "action": latest_decision.action,
            "reason": latest_decision.reason,
        }

    return {
        "id": str(row.id),
        "content_id": str(version.content_id),
        "version_no": version.version_no,
        "span": {"start": row.span_start, "end": row.span_end, "page": None},
        "category": row.category,
        "severity": row.severity,
        "check_type": row.check_type,
        "status": status,
        "confidence": row.confidence,
        "source": (
            {"type": source_type, "id": str(source_id), "clause_text": clause_text}
            if valid_source and source_type and source_id
            else None
        ),
        "explanation": row.explanation,
        "suggestion": (
            {"text": row.suggestion_text, "intent_preserved": bool(row.intent_preserved)}
            if row.suggestion_text
            else None
        ),
        "decision": decision,
    }


def review_ai_services(db: Session, version_id: UUID) -> list[str]:
    rows = db.query(AIUsageLog.service).filter(
        AIUsageLog.content_version_id == version_id
    ).order_by(AIUsageLog.created_at.asc()).all()
    return list(dict.fromkeys(service for (service,) in rows))


def review_engine_status(db: Session, version_id: UUID) -> str:
    blocked = db.query(AIUsageLog.id).filter(
        AIUsageLog.content_version_id == version_id,
        AIUsageLog.blocked.is_(True),
    ).first()
    return "degraded" if blocked else "ok"


def run_and_persist_review(
    db: Session,
    user: User,
    content: ContentItem,
    version: ContentVersion,
    additional_findings: list[Any] | None = None,
    progress_callback=None,
    raise_ai_errors: bool = False,
) -> dict[str, Any]:
    existing_rows = db.query(Finding).filter(Finding.content_version_id == version.id).all()
    if version.status == "reviewed" and content.status != "needs_recheck":
        usage_rows = db.query(AIUsageLog).filter(AIUsageLog.content_version_id == version.id).all()
        return {
            "findings": [serialize_finding(db, row, version, user.organisation_id) for row in existing_rows],
            "engine_status": "degraded" if any(item.blocked for item in usage_rows) else "ok",
            "ai_services_used": list(dict.fromkeys(item.service for item in usage_rows)),
            "cached": True,
        }
    existing_keys = {
        (
            row.span_start,
            row.span_end,
            row.category,
            row.severity,
            row.check_type,
            row.status,
            row.source_type,
            str(row.source_id) if row.source_id else None,
            row.explanation,
        )
        for row in existing_rows
    }

    rules = _rule_sources(db, user.organisation_id)
    facts = _fact_sources(db, user.organisation_id)
    retriever_mode = settings.RETRIEVER.strip().casefold()
    if retriever_mode == "pgvector":
        retriever = PgVectorRetriever(db, user.organisation_id)
    elif retriever_mode == "memory":
        retriever = None
    else:
        raise ValueError(f"Unsupported RETRIEVER mode: {settings.RETRIEVER}")
    result = review_text(
        version.body,
        version.intent,
        rules,
        facts,
        content_id=str(content.id),
        version_no=version.version_no,
        channel=version.channel,
        retriever=retriever,
        progress_callback=progress_callback,
        raise_ai_errors=raise_ai_errors,
    )
    findings = list(result["findings"]) + list(additional_findings or [])
    valid_source_ids = {
        ("rule", str(source["id"])) for source in rules
    } | {
        ("fact", str(source["id"])) for source in facts
    }

    for item in findings:
        payload = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        source = payload.get("source") or {}
        source_type = source.get("type")
        try:
            source_id = UUID(str(source.get("id"))) if source.get("id") else None
        except (TypeError, ValueError):
            source_id = None
        source_valid = bool(
            source_type
            and source_id
            and (source_type, str(source_id)) in valid_source_ids
        )
        finding_status = payload.get("status", "cannot_verify")
        if finding_status == "violation" and not source_valid:
            finding_status = "cannot_verify"
            source_type = None
            source_id = None

        span = payload.get("span") or {}
        suggestion = payload.get("suggestion")
        span_start = max(0, int(span.get("start", 0)))
        span_end = max(0, int(span.get("end", 0)))
        explanation = str(payload.get("explanation", "A human review is required."))
        finding_key = (
            span_start,
            span_end,
            str(payload.get("category", "messaging")),
            str(payload.get("severity", "medium")),
            str(payload.get("check_type", "retrieval_ai")),
            finding_status,
            source_type if source_valid else None,
            str(source_id) if source_valid and source_id else None,
            explanation,
        )
        if finding_key in existing_keys:
            continue
        existing_keys.add(finding_key)
        db.add(Finding(
            id=UUID(str(payload["id"])),
            content_version_id=version.id,
            span_start=span_start,
            span_end=span_end,
            category=str(payload.get("category", "messaging")),
            severity=str(payload.get("severity", "medium")),
            check_type=str(payload.get("check_type", "retrieval_ai")),
            status=finding_status,
            confidence=max(0.0, min(1.0, float(payload.get("confidence", 0.0)))),
            source_type=source_type if source_valid else None,
            source_id=source_id if source_valid else None,
            explanation=explanation,
            suggestion_text=suggestion.get("text") if isinstance(suggestion, dict) else None,
            intent_preserved=bool(suggestion.get("intent_preserved", False)) if isinstance(suggestion, dict) else False,
        ))

    existing_usage = {
        row.fact_id
        for row in db.query(FactUsage).filter(FactUsage.content_version_id == version.id)
    }
    for usage in result.get("fact_usage", []):
        try:
            fact_id = UUID(str(usage["fact_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        if fact_id not in existing_usage:
            db.add(FactUsage(content_version_id=version.id, fact_id=fact_id))
            existing_usage.add(fact_id)

    for usage in result.get("ai_usage", []):
        db.add(AIUsageLog(
            organisation_id=user.organisation_id,
            content_version_id=version.id,
            service=str(usage.get("service", "unknown")),
            purpose=str(usage.get("purpose", "content_review")),
            redacted_bool=bool(usage.get("redacted")),
            external=bool(usage.get("external")),
            blocked=bool(usage.get("blocked")),
        ))

    version.status = "reviewed"
    db.flush()
    rows = db.query(Finding).filter(Finding.content_version_id == version.id).all()
    engine_status = "degraded" if any(item.get("blocked") for item in result.get("ai_usage", [])) else "ok"
    return {
        "findings": [serialize_finding(db, row, version, user.organisation_id) for row in rows],
        "engine_status": engine_status,
        "ai_services_used": result.get("ai_services_used", []),
        "ai_skipped_reason": result.get("ai_skipped_reason"),
        "cached": False,
        "pipeline": {
            "retrieved_source_ids": result.get("retrieved_source_ids", []),
            "privacy": result.get("privacy", {}),
        },
    }
