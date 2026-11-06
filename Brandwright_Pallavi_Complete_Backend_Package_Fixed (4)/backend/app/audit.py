from sqlalchemy.orm import Session
from app.models import AuditLog
from typing import Optional

def log_audit(db: Session, org_id: str, action: str, entity_type: str, user_id: Optional[str] = None, entity_id: Optional[str] = None, details: Optional[str] = None):
    audit = AuditLog(
        organisation_id=org_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details
    )
    db.add(audit)
    db.flush()
    return audit
