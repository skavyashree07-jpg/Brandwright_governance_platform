from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import ContentVersion, ReviewEvent

TERMINAL_REVIEW_STATUSES = {"completed", "failed"}
REVIEW_STATUS_TRANSITIONS = {
    "queued": {"queued", "running", "failed"},
    "running": {"running", "completed", "failed"},
    "completed": {"completed"},
    "failed": {"failed"},
}


def validate_review_transition(current: str | None, next_status: str) -> None:
    if next_status not in REVIEW_STATUS_TRANSITIONS:
        raise ValueError(f"Invalid review job status: {next_status}")
    if current and next_status not in REVIEW_STATUS_TRANSITIONS.get(current, set()):
        raise ValueError(f"Illegal review status transition: {current} -> {next_status}")


def record_review_event(
    db: Session,
    version: ContentVersion,
    organisation_id,
    status: str,
    stage: str,
    message: str,
    findings: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReviewEvent:
    validate_review_transition(version.review_job_status, status)
    version.review_job_status = status
    version.review_stage = stage
    event = ReviewEvent(
        organisation_id=organisation_id,
        content_version_id=version.id,
        status=status,
        stage=stage,
        message=message,
        findings=findings or [],
        metadata_json=metadata or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def is_terminal_review_status(status: str) -> bool:
    return status in TERMINAL_REVIEW_STATUSES
