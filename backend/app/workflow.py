from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import ContentItem, ContentVersion, AuditLog, Alert, FactUsage

VALID_TRANSITIONS = {
    "draft": ["submitted", "in_review"],
    "submitted": ["queued", "draft"],
    "queued": ["in_review", "changes_requested", "rejected"],
    "in_review": ["approved", "changes_requested", "rejected", "queued"],
    "changes_requested": ["resubmitted", "draft"],
    "resubmitted": ["queued", "draft"],
    "approved": ["archived"],
    "rejected": ["archived", "draft"],
    "archived": [],
    "needs_recheck": ["in_review", "draft", "submitted"],
}

REVIEWER_ROLES = {"reviewer", "admin", "manager"}
CREATOR_ROLES = {"creator", "admin"}
STRICT_ROLE_TRANSITIONS = {
    "creator": {"draft": {"submitted"}, "changes_requested": {"resubmitted"}, "needs_recheck": {"submitted", "draft"}},
    "reviewer": {"submitted": {"queued"}, "queued": {"in_review", "changes_requested", "rejected"}, "in_review": {"approved", "changes_requested", "rejected", "queued"}, "resubmitted": {"queued"}},
    "manager": {"submitted": {"queued"}, "queued": {"in_review", "changes_requested", "rejected"}, "in_review": {"approved", "changes_requested", "rejected", "queued"}, "resubmitted": {"queued"}},
    "admin": {"draft": {"submitted", "in_review"}, "submitted": {"queued", "draft"}, "queued": {"in_review", "changes_requested", "rejected"}, "in_review": {"approved", "changes_requested", "rejected", "queued"}, "changes_requested": {"resubmitted", "draft"}, "resubmitted": {"queued", "draft"}, "needs_recheck": {"in_review", "draft", "submitted"}},
}


def ensure_version_history_is_immutable(db: Session, content: ContentItem, version_no: int) -> None:
    existing = (
        db.query(ContentVersion)
        .filter(ContentVersion.content_id == content.id, ContentVersion.version_no == version_no)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version {version_no} already exists and cannot be rewritten.",
        )
    if version_no <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Version numbers must be positive integers.",
        )
    if content.current_version_no and version_no <= content.current_version_no:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="New content versions must advance the version history in order.",
        )


def transition_content_status(
    db: Session,
    content: ContentItem,
    new_status: str,
    user_id: str,
    org_id: str,
    user_role: str | None = None,
    allowed_roles: set[str] | None = None,
):
    current = content.status
    if new_status not in VALID_TRANSITIONS.get(current, []):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Illegal state transition from '{current}' to '{new_status}'."
        )

    if user_role is not None:
        if allowed_roles is not None:
            allowed = allowed_roles
        else:
            allowed = STRICT_ROLE_TRANSITIONS.get(user_role, {}).get(current, set())
            if not allowed and new_status in {"approved", "rejected", "changes_requested"}:
                allowed = REVIEWER_ROLES
            elif not allowed and current in {"draft", "changes_requested", "needs_recheck"}:
                allowed = CREATOR_ROLES
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' cannot transition content from '{current}' to '{new_status}'.",
            )

    if new_status in {"approved", "rejected", "changes_requested"} and user_role is not None and user_role not in REVIEWER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only reviewers/admins can perform '{new_status}' transitions.",
        )

    content.status = new_status

    audit = AuditLog(
        organisation_id=org_id,
        user_id=user_id,
        action=f"STATUS_CHANGE_{new_status.upper()}",
        entity_type="content_item",
        entity_id=content.id,
        details=f"Transitioned from {current} to {new_status}",
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
