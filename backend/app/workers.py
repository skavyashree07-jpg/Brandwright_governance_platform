from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx
from anthropic import APIConnectionError, APITimeoutError, APIStatusError
from redis import Redis
from rq import Queue, Retry, get_current_job
from rq.timeouts import JobTimeoutException

from app.config import settings
from app.db import SessionLocal
from app.models import ContentItem, ContentVersion, User
from app.review.integration import run_and_persist_review
from app.review.ingestion import extract_file
from app.review.image_review import inspect_uploaded_image
from app.review.progress import record_review_event
from app.storage import read_file


redis_conn = Redis.from_url(settings.REDIS_URL)
review_queue = Queue("reviews", connection=redis_conn)
USER_REVIEW_ERROR = "The review could not be completed. Please retry in a moment."
RETRY_REVIEW_MESSAGE = "A temporary review-service issue occurred. Retrying shortly."


def enqueue_review(content_version_id: UUID, user_id: UUID, job_id: str, extra_findings=None):
    return review_queue.enqueue(
        "app.workers.process_review_job",
        str(content_version_id),
        str(user_id),
        extra_findings or [],
        job_id=job_id,
        job_timeout=settings.REVIEW_JOB_TIMEOUT_SECONDS,
        retry=Retry(max=3, interval=[5, 15, 30]),
        result_ttl=600,
        failure_ttl=3600,
        on_failure=handle_review_failure,
    )


def is_retryable_review_error(exc: Exception) -> bool:
    if isinstance(exc, (
        TimeoutError, ConnectionError, httpx.TransportError, APIConnectionError,
        APITimeoutError, JobTimeoutException,
    )):
        return True
    return isinstance(exc, APIStatusError) and exc.status_code >= 500


def should_retry_review(exc: Exception, retries_left: int | None) -> bool:
    return is_retryable_review_error(exc) and bool(retries_left and retries_left > 0)


def process_review_job(content_version_id: str, user_id: str, extra_findings=None):
    db = SessionLocal()
    version_id = UUID(content_version_id)
    actor_id = UUID(user_id)
    try:
        version = db.query(ContentVersion).filter(ContentVersion.id == version_id).first()
        user = db.query(User).filter(User.id == actor_id).first()
        if not version or not user:
            raise ValueError("Review job references a missing version or user.")
        content = db.query(ContentItem).filter(
            ContentItem.id == version.content_id,
            ContentItem.organisation_id == user.organisation_id,
        ).first()
        if not content:
            raise ValueError("Review job content is outside the actor's organisation.")
        version.status = "running"
        record_review_event(
            db, version, user.organisation_id, "running", "extraction", "Preparing submitted content."
        )
        image_findings = []
        if version.source_file_key:
            file_bytes = read_file(version.source_file_key)
            filename = Path(version.source_file_key).name
            extraction = extract_file(file_bytes, filename)
            suffix = Path(filename).suffix.casefold()
            version.body = extraction.text.strip() or (
                f"[Image upload: {filename}]" if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"} else ""
            )
            if not version.body.strip():
                raise ValueError("No text could be extracted from the uploaded file.")
            if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
                image_findings = inspect_uploaded_image(
                    db, user.organisation_id, str(content.id), version.version_no,
                    file_bytes, version.source_alt_text,
                )
            db.commit()
            record_review_event(
                db,
                version,
                user.organisation_id,
                "running",
                "extraction",
                "Content extraction completed.",
                findings=[item.to_dict() for item in image_findings],
                metadata={"extracted_text": version.body, "warnings": extraction.warnings},
            )
        else:
            record_review_event(
                db,
                version,
                user.organisation_id,
                "running",
                "extraction",
                "Text content is ready for review.",
                metadata={"extracted_text": version.body, "warnings": []},
            )

        def publish_stage(stage: str, stage_status: str, findings):
            payload = [
                item.to_dict() if hasattr(item, "to_dict") else dict(item)
                for item in findings
            ]
            record_review_event(
                db,
                version,
                user.organisation_id,
                "running",
                stage,
                f"{stage.replace('_', ' ').capitalize()} {'completed' if stage_status == 'completed' else stage_status}.",
                findings=payload,
            )

        result = run_and_persist_review(
            db,
            user,
            content,
            version,
            additional_findings=list(extra_findings or []) + image_findings,
            progress_callback=publish_stage,
            raise_ai_errors=True,
        )
        version.review_error = None
        db.commit()
        record_review_event(
            db, version, user.organisation_id, "completed", "completed",
            "Review completed.", findings=result["findings"],
            metadata={
                "engine_status": result.get("engine_status", "ok"),
                "ai_services_used": result.get("ai_services_used", []),
            },
        )
        return result
    except Exception as exc:
        db.rollback()
        actor = db.query(User).filter(User.id == actor_id).first()
        failed_version = None
        if actor:
            failed_version = db.query(ContentVersion).join(ContentItem).filter(
                ContentVersion.id == version_id,
                ContentItem.organisation_id == actor.organisation_id,
            ).first()
        current_job = get_current_job()
        retryable = is_retryable_review_error(exc)
        retries_left = current_job.retries_left if current_job else 0
        will_retry = should_retry_review(exc, retries_left)
        if failed_version and actor:
            failed_version.status = "queued" if will_retry else "failed"
            failed_version.review_error = None if will_retry else USER_REVIEW_ERROR
            record_review_event(
                db,
                failed_version,
                actor.organisation_id,
                "running" if will_retry else "failed",
                failed_version.review_stage or "review",
                RETRY_REVIEW_MESSAGE if will_retry else USER_REVIEW_ERROR,
            )
            db.commit()
        if will_retry:
            raise
        return {"status": "failed", "review_error": USER_REVIEW_ERROR}
    finally:
        db.close()


def handle_review_failure(job, connection, exc_type, exc_value, traceback):
    """Keep timeout retries live and mark terminal RQ failures in the database."""
    try:
        version_id = UUID(job.args[0])
        user_id = UUID(job.args[1])
    except (IndexError, TypeError, ValueError):
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        version = None
        if user:
            version = db.query(ContentVersion).join(ContentItem).filter(
                ContentVersion.id == version_id,
                ContentItem.organisation_id == user.organisation_id,
            ).first()
        if not version or not user:
            return
        will_retry = should_retry_review(exc_value, job.retries_left)
        version.status = "queued" if will_retry else "failed"
        version.review_error = None if will_retry else USER_REVIEW_ERROR
        record_review_event(
            db,
            version,
            user.organisation_id,
            "running" if will_retry else "failed",
            version.review_stage or "review",
            RETRY_REVIEW_MESSAGE if will_retry else USER_REVIEW_ERROR,
        )
        db.commit()
    finally:
        db.close()
