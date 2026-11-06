from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Rule
from app.review.schemas import Finding, TextSpan
from app.review.visual_checks import inspect_image


def inspect_uploaded_image(
    db: Session,
    organisation_id,
    content_id: str,
    version_no: int,
    image_bytes: bytes,
    alt_text: str | None,
) -> list[Finding]:
    inspection = inspect_image(image_bytes, alt_text=alt_text)
    findings = []
    for item in inspection["findings"]:
        rule = db.query(Rule).filter(
            Rule.organisation_id == organisation_id,
            Rule.status == "approved",
            Rule.category == item["category"],
        ).first()
        source = (
            {"type": "rule", "id": str(rule.id), "clause_text": rule.text}
            if rule else None
        )
        findings.append(Finding(
            id=str(uuid4()),
            content_id=content_id,
            version_no=version_no,
            span=TextSpan(0, 0, page=1),
            category=item["category"],
            severity=item["severity"],
            check_type=item["check_type"],
            status="violation" if source else "cannot_verify",
            confidence=1.0,
            source=source,
            explanation=item["explanation"],
            suggestion=None,
        ))
    return findings
