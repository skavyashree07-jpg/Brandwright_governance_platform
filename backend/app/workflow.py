from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import ContentItem, ContentVersion, AuditLog, Alert, FactUsage

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
    usages = db.query(FactUsage).join(FactUsage.content_version).join(
        ContentVersion.content_item
    ).filter(
        FactUsage.fact_id == fact_id,
        ContentItem.organisation_id == org_id,
    ).all()
    affected_content_ids = set()
    affected_version_ids = set()
    for usage in usages:
        version = usage.content_version
        if version and version.content_item:
            if version.id in affected_version_ids:
                continue
            affected_version_ids.add(version.id)
            content_item = version.content_item
            first_for_content = content_item.id not in affected_content_ids
            affected_content_ids.add(content_item.id)
            prior_status = content_item.status if first_for_content else None
            content_item.status = "needs_recheck"
            version.status = "needs_recheck"
            if first_for_content:
                existing = db.query(Alert.id).filter(
                    Alert.organisation_id == org_id,
                    Alert.alert_type == "fact_drift",
                    Alert.ref_id == content_item.id,
                    Alert.status == "active",
                ).first()
                if not existing:
                    db.add(Alert(
                        organisation_id=org_id,
                        alert_type="fact_drift",
                        ref_id=content_item.id,
                        status="active",
                        prior_status=prior_status,
                    ))
    db.flush()
