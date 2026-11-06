from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import ContentItem, AuditLog, Alert, FactUsage

VALID_TRANSITIONS = {
    "draft": ["in_review"],
    "in_review": ["changes_requested", "approved"],
    "changes_requested": ["in_review", "draft"],
    "approved": [],
    "needs_recheck": ["in_review", "draft"]
}

def transition_content_status(db: Session, content: ContentItem, new_status: str, user_id: str, org_id: str):
    current = content.status
    if new_status not in VALID_TRANSITIONS.get(current, []):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Illegal state transition from '{current}' to '{new_status}'."
        )
    content.status = new_status
    
    audit = AuditLog(
        organisation_id=org_id,
        user_id=user_id,
        action=f"STATUS_CHANGE_{new_status.upper()}",
        entity_type="content_item",
        entity_id=content.id,
        details=f"Transitioned from {current} to {new_status}"
    )
    db.add(audit)
    db.flush()
    return content

def trigger_fact_drift_alerts(db: Session, fact_id: str, org_id: str):
    usages = db.query(FactUsage).filter(FactUsage.fact_id == fact_id).all()
    for usage in usages:
        version = usage.content_version
        if version and version.content_item:
            content_item = version.content_item
            content_item.status = "needs_recheck"
            
            alert = Alert(
                organisation_id=org_id,
                alert_type="fact_drift",
                ref_id=content_item.id,
                status="active"
            )
            db.add(alert)
    db.flush()
