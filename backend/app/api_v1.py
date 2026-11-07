from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from redis.exceptions import RedisError
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from redis import Redis

from app.audit import log_audit
from app.config import DEMO_ORGANISATION_NAME, DEMO_USER_EMAILS, settings
from app.db import SessionLocal, get_db
from app.insights.guideline_drafting import calculate_guideline_health, draft_rule_clarification
from app.models import (
    AIUsageLog,
    Alert,
    Asset,
    AuditLog,
    Comment,
    ContentItem,
    ContentVersion,
    Fact,
    Finding,
    FindingDecision,
    GuidelineDoc,
    Organisation,
    Rule,
    RuleClarification,
    ReviewEvent,
    Term,
    User,
)
from app.review.brandbook import parse_brand_book
from app.review.embeddings import create_embedder, term_embedding_text
from app.review.ingestion import extract_file
from app.review.progress import is_terminal_review_status, record_review_event
from app.review.integration import (
    review_ai_services,
    review_engine_status,
    run_and_persist_review,
    serialize_finding,
)
from app.review.pipeline import review_text
from app.review.schemas import Finding as EngineFinding, TextSpan
from app.review.visual_checks import inspect_image
from app.schemas import (
    AssetCreateSchema,
    ClarificationUpdateSchema,
    CommentCreateSchema,
    ContentCreateSchema,
    ContentVersionCreateSchema,
    DemoLoginSchema,
    FactCreateSchema,
    FactUpdateSchema,
    FindingDecisionCreateSchema,
    LoginSchema,
    RuleCreateSchema,
    TermCreateSchema,
    TokenSchema,
    UserSchema,
)
from app.security import (
    create_access_token,
    get_current_user,
    get_jury_session_claims,
    get_token_payload,
    require_role,
    verify_password,
)
from app.storage import StorageUnavailable, read_file, store_file
from app.trust.evaluator import evaluate_dataset
from app.workflow import transition_content_status, trigger_fact_drift_alerts
from app.workers import enqueue_review

api_router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".txt", ".md", ".csv", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
DEMO_LOGIN_LIMIT = 10
DEMO_LOGIN_WINDOW_SECONDS = 60
_demo_login_attempts: dict[str, list[float]] = {}
_demo_login_lock = threading.Lock()
_demo_login_redis = Redis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=0.2,
    socket_timeout=0.2,
)
_DEMO_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) >= limit then
  return 0
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('EXPIRE', key, window)
return 1
"""


def _enforce_demo_login_limit(client_ip: str, now: float | None = None) -> None:
    current_time = now if now is not None else time.monotonic()
    redis_time = time.time()
    ip_key = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
    try:
        allowed = _demo_login_redis.eval(
            _DEMO_RATE_LIMIT_SCRIPT,
            1,
            f"brandwright:demo-login:{ip_key}",
            redis_time,
            DEMO_LOGIN_WINDOW_SECONDS,
            DEMO_LOGIN_LIMIT,
            f"{redis_time}:{uuid4()}",
        )
    except RedisError:
        logger.warning("Demo login rate limiting is using process-local storage because Redis is unavailable.")
        allowed = None
    if allowed is not None:
        if int(allowed) == 0:
            raise HTTPException(
                status_code=429,
                detail="Too many demo sign-in attempts. Please wait a minute and try again.",
                headers={"Retry-After": str(DEMO_LOGIN_WINDOW_SECONDS)},
            )
        return

    with _demo_login_lock:
        recent_attempts = [
            stamp for stamp in _demo_login_attempts.get(client_ip, [])
            if current_time - stamp < DEMO_LOGIN_WINDOW_SECONDS
        ]
        if len(recent_attempts) >= DEMO_LOGIN_LIMIT:
            _demo_login_attempts[client_ip] = recent_attempts
            raise HTTPException(
                status_code=429,
                detail="Too many demo sign-in attempts. Please wait a minute and try again.",
                headers={"Retry-After": str(DEMO_LOGIN_WINDOW_SECONDS)},
            )
        recent_attempts.append(current_time)
        _demo_login_attempts[client_ip] = recent_attempts
        if len(_demo_login_attempts) > 1024:
            for ip, attempts in tuple(_demo_login_attempts.items()):
                if not attempts or current_time - attempts[-1] >= DEMO_LOGIN_WINDOW_SECONDS:
                    _demo_login_attempts.pop(ip, None)


def _access_token_response(
    user: User,
    jury_session_id: UUID | None = None,
    expires_delta: timedelta | None = None,
) -> dict[str, str]:
    claims = {
        "sub": str(user.id),
        "org_id": str(user.organisation_id),
        "role": user.role,
    }
    if jury_session_id is not None:
        claims.update({
            "session_type": "jury_demo",
            "jury_session_id": str(jury_session_id),
        })
    token = create_access_token(claims, expires_delta=expires_delta)
    return {"access_token": token, "token_type": "bearer"}


def _demo_user_for_role(db: Session, role: str) -> User:
    organisation = db.query(Organisation).filter(
        Organisation.name == DEMO_ORGANISATION_NAME
    ).first()
    if organisation is None:
        raise HTTPException(
            status_code=503,
            detail="Demo accounts are not ready yet. Please try again later.",
        )
    user = db.query(User).filter(
        User.organisation_id == organisation.id,
        User.email == DEMO_USER_EMAILS[role],
        User.role == role,
    ).first()
    if user is None:
        raise HTTPException(
            status_code=503,
            detail="Demo accounts are not ready yet. Please try again later.",
        )
    return user


def _content_or_404(db: Session, content_id: UUID, user: User) -> ContentItem:
    content = db.query(ContentItem).filter(
        ContentItem.id == content_id,
        ContentItem.organisation_id == user.organisation_id,
    ).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return content


def _latest_version(db: Session, content: ContentItem) -> ContentVersion:
    version = db.query(ContentVersion).filter(
        ContentVersion.content_id == content.id,
        ContentVersion.version_no == content.current_version_no,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Content version not found")
    return version


def _content_payload(db: Session, content: ContentItem) -> dict[str, Any]:
    versions = (
        db.query(ContentVersion)
        .filter(ContentVersion.content_id == content.id)
        .order_by(ContentVersion.version_no.desc())
        .all()
    )
    current = next((version for version in versions if version.version_no == content.current_version_no), None)
    return {
        "id": str(content.id),
        "title": content.title,
        "current_version_no": content.current_version_no,
        "status": content.status,
        "created_at": content.created_at,
        "body": current.body if current else "",
        "intent": current.intent if current else "",
        "channel": current.channel if current else "general",
        "versions": [
            {
                "version_no": version.version_no,
                "body": version.body,
                "intent": version.intent,
                "channel": version.channel,
                "status": version.status,
                "has_source_file": bool(version.source_file_key),
                "created_at": version.created_at,
            }
            for version in versions
        ],
    }


def _rule_schema(rule: Rule) -> dict[str, Any]:
    return {
        "id": str(rule.id),
        "clause_number": rule.clause_number,
        "text": rule.text,
        "category": rule.category,
        "channels": rule.channels or [],
        "type": rule.type,
        "config": rule.config or {},
        "status": rule.status,
        "version": rule.version,
        "created_at": rule.created_at,
    }


def _make_image_findings(
    db: Session,
    user: User,
    content_id: UUID,
    version_no: int,
    image_bytes: bytes,
    alt_text: str | None,
) -> list[EngineFinding]:
    try:
        inspection = inspect_image(image_bytes, alt_text=alt_text)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Image inspection dependency is unavailable: {exc.name}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not inspect image: {exc}") from exc

    findings: list[EngineFinding] = []
    for item in inspection["findings"]:
        rule = db.query(Rule).filter(
            Rule.organisation_id == user.organisation_id,
            Rule.status == "approved",
            Rule.category == item["category"],
        ).first()
        source = (
            {"type": "rule", "id": str(rule.id), "clause_text": rule.text}
            if rule
            else None
        )
        findings.append(EngineFinding(
            id=str(uuid4()),
            content_id=str(content_id),
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


def _do_review(db: Session, user: User, content: ContentItem, version: ContentVersion, extra=None):
    return run_and_persist_review(db, user, content, version, additional_findings=extra)


def _schedule_review(db: Session, user: User, content: ContentItem, version: ContentVersion, extra=None):
    if version.review_job_status in {"queued", "running"}:
        return {
            "id": version.review_job_id,
            "status": version.review_job_status,
            "stage": version.review_stage,
            "job_id": version.review_job_id,
            "findings": [],
            "engine_status": version.review_job_status,
            "ai_services_used": [],
        }
    job_id = str(uuid4())
    version.status = "queued"
    version.review_job_id = job_id
    version.review_error = None
    version.review_job_status = "queued"
    version.review_stage = "queued"
    log_audit(
        db,
        str(user.organisation_id),
        "QUEUE_CONTENT_REVIEW",
        "content_item",
        str(user.id),
        str(content.id),
    )
    db.commit()
    record_review_event(
        db, version, user.organisation_id, "queued", "queued", "Review added to the queue."
    )
    extra_payload = [
        item.to_dict() if hasattr(item, "to_dict") else item
        for item in (extra or [])
    ]
    try:
        enqueue_review(version.id, user.id, job_id, extra_payload)
    except RedisError:
        logger.warning("Review queue is unavailable; running this review synchronously.")
        if version.source_file_key and not version.body:
            try:
                file_bytes = read_file(version.source_file_key)
                filename = Path(version.source_file_key).name.split("-", 1)[-1]
                version.body = extract_file(file_bytes, filename).text.strip()
            except (StorageUnavailable, RuntimeError, ImportError, ValueError):
                version.status = "failed"
                version.review_error = "The review queue and file store are unavailable. Please try again later."
                record_review_event(
                    db, version, user.organisation_id, "failed", "queue", version.review_error
                )
                return {
                    "id": job_id,
                    "job_id": job_id,
                    "status": "failed",
                    "stage": "queue",
                    "review_error": version.review_error,
                    "findings": [],
                    "engine_status": "failed",
                    "ai_services_used": [],
                }
        record_review_event(
            db,
            version,
            user.organisation_id,
            "running",
            "deterministic_checks",
            "The review queue is unavailable. Running the review synchronously.",
        )
        result = _do_review(db, user, content, version, extra_payload)
        record_review_event(
            db,
            version,
            user.organisation_id,
            "completed",
            "completed",
            "Review completed using synchronous fallback because the queue was unavailable.",
            findings=result["findings"],
        )
        log_audit(
            db, str(user.organisation_id), "RUN_CONTENT_REVIEW",
            "content_item", str(user.id), str(content.id),
            details="Synchronous fallback because the review queue was unavailable.",
        )
        db.commit()
        return {
            "id": job_id,
            "job_id": job_id,
            "status": "completed",
            "stage": "completed",
            "findings": result["findings"],
            "engine_status": result.get("engine_status", "completed"),
            "ai_services_used": result.get("ai_services_used", []),
        }
    return {
        "id": job_id,
        "status": "queued",
        "stage": "queued",
        "job_id": job_id,
        "findings": [],
        "engine_status": "queued",
        "ai_services_used": [],
    }


@api_router.post("/auth/login", response_model=TokenSchema)
def login(payload: LoginSchema, request: Request, db: Session = Depends(get_db)):
    if settings.DEMO_MODE.casefold() == "true":
        _enforce_demo_login_limit(request.client.host if request.client else "unknown")
        user = _demo_user_for_role(db, "creator")
        log_audit(
            db,
            str(user.organisation_id),
            "demo_login",
            "user",
            str(user.id),
            str(user.id),
            details="role=creator",
        )
        db.commit()
        return _access_token_response(user)

    user = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return _access_token_response(user)


@api_router.post("/auth/demo-login", response_model=TokenSchema)
def demo_login(payload: DemoLoginSchema, request: Request, db: Session = Depends(get_db)):
    if settings.DEMO_MODE.casefold() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    _enforce_demo_login_limit(request.client.host if request.client else "unknown")
    user = _demo_user_for_role(db, payload.role)

    log_audit(
        db,
        str(user.organisation_id),
        "demo_login",
        "user",
        str(user.id),
        str(user.id),
        details=f"role={user.role}",
    )
    db.commit()
    return _access_token_response(user)


@api_router.post("/auth/jury-demo-login", response_model=TokenSchema)
def jury_demo_login(request: Request, db: Session = Depends(get_db)):
    if not settings.JURY_DEMO_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")

    _enforce_demo_login_limit(request.client.host if request.client else "unknown")
    user = _demo_user_for_role(db, "admin")
    log_audit(
        db,
        str(user.organisation_id),
        "jury_demo_login",
        "user",
        str(user.id),
        str(user.id),
        details="role=admin",
    )
    db.commit()
    return _access_token_response(user, jury_session_id=uuid4())


@api_router.post("/auth/jury-switch-role", response_model=TokenSchema)
def jury_switch_role(
    payload: DemoLoginSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    jury_claims: dict[str, Any] = Depends(get_jury_session_claims),
):
    target_user = _demo_user_for_role(db, payload.role)
    if current_user.organisation_id != target_user.organisation_id:
        raise HTTPException(status_code=403, detail="Jury sessions are restricted to the demo organisation")

    expires_delta = datetime.fromtimestamp(
        jury_claims["exp"],
        tz=timezone.utc,
    ) - datetime.now(timezone.utc)
    if expires_delta <= timedelta(0):
        raise HTTPException(status_code=401, detail="Jury demo session has expired")

    log_audit(
        db,
        str(current_user.organisation_id),
        "jury_demo_role_switch",
        "user",
        str(current_user.id),
        str(target_user.id),
        details=f"role={target_user.role}",
    )
    db.commit()
    return _access_token_response(
        target_user,
        jury_session_id=UUID(jury_claims["jury_session_id"]),
        expires_delta=expires_delta,
    )


@api_router.get("/auth/me", response_model=UserSchema)
def get_me(
    current_user: User = Depends(get_current_user),
    token_payload: dict[str, Any] = Depends(get_token_payload),
):
    profile = UserSchema.model_validate(current_user)
    return profile.model_copy(update={"jury_demo": token_payload.get("session_type") == "jury_demo"})


@api_router.post("/kb/guidelines", status_code=status.HTTP_201_CREATED)
async def upload_guideline(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    filename = Path(file.filename or "guideline").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix or 'unknown'}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES}-byte upload limit")
    try:
        extraction = extract_file(data, filename)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Parser dependency is unavailable: {exc.name}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not extract guideline text: {exc}") from exc
    if not extraction.text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the guideline")
    try:
        file_key = store_file(
            str(current_user.organisation_id),
            "guidelines",
            filename,
            data,
            file.content_type,
        )
    except (StorageUnavailable, RuntimeError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    document = GuidelineDoc(
        organisation_id=current_user.organisation_id,
        title=filename,
        file_path=file_key,
    )
    db.add(document)
    db.flush()
    drafts = parse_brand_book(extraction.text)
    rules = []
    embedder = create_embedder()
    for draft in drafts:
        rule = Rule(
            organisation_id=current_user.organisation_id,
            guideline_id=document.id,
            clause_number=draft["clause_number"] or f"DRAFT-{len(rules) + 1:03d}",
            text=draft["text"],
            category=draft["category"],
            channels=draft["channel_tags"] or ["all"],
            status="pending",
            embedding=embedder.embed(draft["text"]),
        )
        db.add(rule)
        rules.append(rule)
    log_audit(
        db,
        str(current_user.organisation_id),
        "UPLOAD_GUIDELINE",
        "guideline_doc",
        str(current_user.id),
        str(document.id),
        f"Extracted {len(rules)} draft rules from {filename}",
    )
    db.commit()
    return {
        "id": str(document.id),
        "title": document.title,
        "created_at": document.created_at,
        "extraction_warnings": extraction.warnings,
        "rules": [_rule_schema(rule) for rule in rules],
    }


@api_router.get("/kb/rules")
def list_rules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(Rule).filter(Rule.organisation_id == current_user.organisation_id).all()
    return [_rule_schema(rule) for rule in rows]


@api_router.post("/kb/rules", status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    embedding = create_embedder().embed(payload.text)
    rule = Rule(
        organisation_id=current_user.organisation_id,
        clause_number=payload.clause_number,
        text=payload.text,
        category=payload.category,
        channels=payload.channels,
        type=payload.type,
        config=payload.config,
        status="pending",
        embedding=embedding,
    )
    db.add(rule)
    db.flush()
    log_audit(db, str(current_user.organisation_id), "CREATE_RULE", "rule", str(current_user.id), str(rule.id))
    db.commit()
    db.refresh(rule)
    return _rule_schema(rule)


@api_router.patch("/kb/rules/{rule_id}")
def update_rule(
    rule_id: UUID,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    rule = db.query(Rule).filter(
        Rule.id == rule_id,
        Rule.organisation_id == current_user.organisation_id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    allowed = {"clause_number", "text", "category", "channels", "type", "config", "status"}
    unknown = set(payload) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported rule fields: {', '.join(sorted(unknown))}")
    if "text" in payload and (not isinstance(payload["text"], str) or not payload["text"].strip()):
        raise HTTPException(status_code=422, detail="Rule text must be a non-empty string")
    if "status" in payload and payload["status"] not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Rule status must be pending, approved, or rejected")
    previous_text = rule.text
    for key, value in payload.items():
        setattr(rule, key, value)
    if rule.text != previous_text:
        rule.embedding = create_embedder().embed(rule.text)
    rule.version += 1
    log_audit(db, str(current_user.organisation_id), "UPDATE_RULE", "rule", str(current_user.id), str(rule.id))
    db.commit()
    db.refresh(rule)
    return _rule_schema(rule)


@api_router.get("/kb/facts")
def list_facts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Fact).filter(Fact.organisation_id == current_user.organisation_id).all()


@api_router.post("/kb/facts", status_code=status.HTTP_201_CREATED)
def create_fact(
    payload: FactCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    fact_data = payload.model_dump()
    fact = Fact(
        organisation_id=current_user.organisation_id,
        **fact_data,
        embedding=create_embedder().embed(fact_data["text"]),
    )
    db.add(fact)
    db.flush()
    log_audit(db, str(current_user.organisation_id), "CREATE_FACT", "fact", str(current_user.id), str(fact.id))
    db.commit()
    db.refresh(fact)
    return fact


@api_router.patch("/kb/facts/{fact_id}")
def update_fact(
    fact_id: UUID,
    payload: FactUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    fact = db.query(Fact).filter(
        Fact.id == fact_id,
        Fact.organisation_id == current_user.organisation_id,
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") not in {None, "approved", "expired", "rejected"}:
        raise HTTPException(status_code=422, detail="Fact status must be approved, expired, or rejected")
    for key, value in changes.items():
        setattr(fact, key, value)
    if "text" in changes:
        fact.embedding = create_embedder().embed(fact.text)
    fact.version += 1
    trigger_fact_drift_alerts(db, str(fact.id), str(current_user.organisation_id))
    log_audit(
        db,
        str(current_user.organisation_id),
        "UPDATE_FACT_DRIFT_TRIGGERED",
        "fact",
        str(current_user.id),
        str(fact.id),
    )
    db.commit()
    db.refresh(fact)
    return fact


@api_router.get("/kb/terms")
def list_terms(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Term).filter(Term.organisation_id == current_user.organisation_id).all()


@api_router.post("/kb/terms", status_code=status.HTTP_201_CREATED)
def create_term(
    payload: TermCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    term_data = payload.model_dump()
    term = Term(
        organisation_id=current_user.organisation_id,
        **term_data,
        embedding=create_embedder().embed(
            term_embedding_text(term_data["preferred"], term_data["banned"], term_data.get("notes"))
        ),
    )
    db.add(term)
    db.flush()
    log_audit(db, str(current_user.organisation_id), "CREATE_TERM", "term", str(current_user.id), str(term.id))
    db.commit()
    db.refresh(term)
    return term


@api_router.patch("/kb/terms/{term_id}")
def update_term(
    term_id: UUID,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    term = db.query(Term).filter(
        Term.id == term_id,
        Term.organisation_id == current_user.organisation_id,
    ).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    allowed = {"preferred", "banned", "notes"}
    unknown = set(payload) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported term fields: {', '.join(sorted(unknown))}")
    if not payload:
        raise HTTPException(status_code=422, detail="At least one term field is required")
    for key, value in payload.items():
        if key in {"preferred", "banned"} and (not isinstance(value, str) or not value.strip()):
            raise HTTPException(status_code=422, detail=f"{key} must be a non-empty string")
        if key == "notes" and value is not None and not isinstance(value, str):
            raise HTTPException(status_code=422, detail="notes must be a string or null")
        setattr(term, key, value)
    term.embedding = create_embedder().embed(
        term_embedding_text(term.preferred, term.banned, term.notes)
    )
    log_audit(db, str(current_user.organisation_id), "UPDATE_TERM", "term", str(current_user.id), str(term.id))
    db.commit()
    db.refresh(term)
    return term


@api_router.get("/kb/assets")
def list_assets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Asset).filter(Asset.organisation_id == current_user.organisation_id).all()


@api_router.post("/kb/assets", status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    asset = Asset(organisation_id=current_user.organisation_id, **payload.model_dump())
    db.add(asset)
    db.flush()
    log_audit(db, str(current_user.organisation_id), "CREATE_ASSET", "asset", str(current_user.id), str(asset.id))
    db.commit()
    db.refresh(asset)
    return asset


@api_router.post("/kb/assets/upload", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    name: str = Form(...),
    metadata_json: str = Form("{}"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES}-byte upload limit")
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="metadata_json must contain valid JSON") from exc
    try:
        object_key = store_file(
            str(current_user.organisation_id),
            "assets",
            Path(file.filename or name).name,
            data,
            file.content_type,
        )
    except (StorageUnavailable, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    asset = Asset(
        organisation_id=current_user.organisation_id,
        name=name,
        file_url=object_key,
        metadata_json=json.dumps(metadata),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@api_router.get("/kb/assets/{asset_id}/file")
def download_asset(asset_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.organisation_id == current_user.organisation_id,
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        data = read_file(asset.file_url)
    except (StorageUnavailable, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=data, media_type="application/octet-stream")


@api_router.post("/content", status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["creator", "admin"])),
):
    content = ContentItem(
        organisation_id=current_user.organisation_id,
        creator_id=current_user.id,
        title=payload.title,
        status="draft",
    )
    db.add(content)
    db.flush()
    version = ContentVersion(
        content_id=content.id,
        version_no=1,
        body=payload.body,
        intent=payload.intent,
        channel=payload.channel or "general",
    )
    db.add(version)
    log_audit(db, str(current_user.organisation_id), "CREATE_CONTENT", "content_item", str(current_user.id), str(content.id))
    db.commit()
    db.refresh(content)
    return content


@api_router.post("/content/upload", status_code=status.HTTP_201_CREATED)
async def upload_content(
    file: UploadFile = File(...),
    title: str = Form(...),
    intent: str = Form(...),
    channel: str = Form("general"),
    alt_text: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["creator", "admin"])),
):
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix or 'unknown'}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES}-byte upload limit")
    extraction = None
    body = ""
    if not settings.REVIEW_ASYNC:
        try:
            extraction = extract_file(data, filename)
        except ImportError as exc:
            raise HTTPException(status_code=503, detail=f"Parser dependency is unavailable: {exc.name}") from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not extract content text: {exc}") from exc
        body = extraction.text.strip() or f"[Image upload: {filename}]"
    storage_warning = None
    try:
        file_key = store_file(
            str(current_user.organisation_id),
            "content",
            filename,
            data,
            file.content_type,
        )
    except (StorageUnavailable, RuntimeError):
        logger.warning("File storage is unavailable; continuing with extracted text only.")
        file_key = None
        storage_warning = "The original file could not be stored. It was reviewed from extracted text only."
        if extraction is None:
            try:
                extraction = extract_file(data, filename)
            except ImportError as parser_error:
                raise HTTPException(
                    status_code=503,
                    detail=f"File storage and parser dependencies are unavailable: {parser_error.name}",
                ) from parser_error
            except Exception as parser_error:
                raise HTTPException(
                    status_code=422,
                    detail=f"File storage is unavailable and content could not be extracted: {parser_error}",
                ) from parser_error
            body = extraction.text.strip() or f"[Image upload: {filename}]"

    content = ContentItem(
        organisation_id=current_user.organisation_id,
        creator_id=current_user.id,
        title=title,
        status="draft",
    )
    db.add(content)
    db.flush()
    version = ContentVersion(
        content_id=content.id,
        version_no=1,
        body=body,
        intent=intent,
        channel=channel or "general",
        source_file_key=file_key,
        source_alt_text=alt_text,
    )
    db.add(version)
    db.flush()
    extra_findings = []
    use_async_review = settings.REVIEW_ASYNC and file_key is not None
    if not use_async_review and suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        extra_findings = _make_image_findings(
            db, current_user, content.id, version.version_no, data, alt_text
        )
    if use_async_review:
        result = _schedule_review(db, current_user, content, version, extra_findings)
    else:
        result = run_and_persist_review(db, current_user, content, version, additional_findings=extra_findings)
    log_audit(db, str(current_user.organisation_id), "UPLOAD_CONTENT", "content_item", str(current_user.id), str(content.id))
    db.commit()
    return {
        **_content_payload(db, content),
        "findings": result["findings"],
        "engine_status": result.get("engine_status", result.get("status", "completed")),
        "review_status": result.get("status", "completed") if use_async_review else "completed",
        "status": result.get("status", "completed") if use_async_review else "completed",
        "job_id": result.get("job_id"),
        "stage": result.get("stage", version.review_stage),
        "review_error": result.get("review_error"),
        "ai_services_used": result.get("ai_services_used", []),
        "extraction_warnings": (extraction.warnings if extraction else []) + ([storage_warning] if storage_warning else []),
        "extracted_text": extraction.text if extraction else None,
    }


@api_router.get("/content")
def list_content(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(ContentItem).filter(
        ContentItem.organisation_id == current_user.organisation_id
    ).order_by(ContentItem.created_at.desc()).all()


@api_router.get("/content/{content_id}")
def get_content(content_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _content_payload(db, _content_or_404(db, content_id, current_user))


@api_router.get("/content/{content_id}/versions")
def list_versions(content_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = _content_or_404(db, content_id, current_user)
    return _content_payload(db, content)["versions"]


@api_router.get("/content/{content_id}/versions/{version_no}/file")
def download_content_file(
    content_id: UUID,
    version_no: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = _content_or_404(db, content_id, current_user)
    version = db.query(ContentVersion).filter(
        ContentVersion.content_id == content.id,
        ContentVersion.version_no == version_no,
    ).first()
    if not version or not version.source_file_key:
        raise HTTPException(status_code=404, detail="Source file not found")
    try:
        data = read_file(version.source_file_key)
    except (StorageUnavailable, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=data, media_type="application/octet-stream")


@api_router.post("/content/{content_id}/versions")
def create_version(
    content_id: UUID,
    payload: ContentVersionCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["creator", "admin"])),
):
    content = _content_or_404(db, content_id, current_user)
    if current_user.role != "admin" and content.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the content creator can create a version")
    if content.status not in {"draft", "changes_requested", "needs_recheck"}:
        raise HTTPException(status_code=409, detail="Content is locked after it enters approval")
    version_no = content.current_version_no + 1
    version = ContentVersion(
        content_id=content.id,
        version_no=version_no,
        body=payload.body,
        intent=payload.intent,
        channel=payload.channel or "general",
    )
    db.add(version)
    content.current_version_no = version_no
    content.status = "draft"
    log_audit(db, str(current_user.organisation_id), "CREATE_CONTENT_VERSION", "content_item", str(current_user.id), str(content.id))
    db.commit()
    db.refresh(content)
    return content


@api_router.post("/content/{content_id}/review")
def review_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["creator", "reviewer", "manager", "admin"])),
):
    content = _content_or_404(db, content_id, current_user)
    version = _latest_version(db, content)
    if settings.REVIEW_ASYNC:
        return _schedule_review(db, current_user, content, version)
    result = _do_review(db, current_user, content, version)
    version.review_job_status = "completed"
    version.review_stage = "completed"
    log_audit(db, str(current_user.organisation_id), "RUN_CONTENT_REVIEW", "content_item", str(current_user.id), str(content.id))
    db.commit()
    return {**result, "id": str(version.id), "status": "completed", "stage": "completed"}


@api_router.get("/content/{content_id}/findings")
def get_findings(content_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = _content_or_404(db, content_id, current_user)
    version = _latest_version(db, content)
    rows = db.query(Finding).filter(Finding.content_version_id == version.id).all()
    return {
        "version_no": version.version_no,
        "status": version.review_job_status or version.status,
        "stage": version.review_stage,
        "job_id": version.review_job_id,
        "review_error": version.review_error,
        "findings": [serialize_finding(db, row, version, current_user.organisation_id) for row in rows],
        "ai_services_used": review_ai_services(db, version.id),
    }


@api_router.get("/reviews/{review_id}")
def get_review(review_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = db.query(ContentItem).filter(
        ContentItem.id == review_id,
        ContentItem.organisation_id == current_user.organisation_id,
    ).first()
    if content:
        version = _latest_version(db, content)
    else:
        version = db.query(ContentVersion).join(ContentItem).filter(
            ContentItem.organisation_id == current_user.organisation_id,
            (ContentVersion.id == review_id) | (ContentVersion.review_job_id == str(review_id)),
        ).first()
        if not version:
            raise HTTPException(status_code=404, detail="Review not found")
        content = version.content_item
    rows = db.query(Finding).filter(Finding.content_version_id == version.id).all()
    review_status = version.review_job_status
    if not review_status:
        review_status = {
            "reviewed": "completed",
            "failed": "failed",
            "queued": "queued",
        }.get(version.status, version.status)
    return {
        "id": version.review_job_id or str(version.id),
        "job_id": version.review_job_id,
        "content_id": str(content.id),
        "version_no": version.version_no,
        "status": review_status,
        "stage": version.review_stage,
        "review_error": version.review_error,
        "engine_status": (
            review_status if review_status in {"queued", "running", "failed"}
            else review_engine_status(db, version.id)
        ),
        "findings": [serialize_finding(db, row, version, current_user.organisation_id) for row in rows],
        "ai_services_used": review_ai_services(db, version.id),
    }


@api_router.get("/reviews/{review_id}/events")
def stream_review_events(
    review_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = db.query(ContentVersion).join(ContentItem).filter(
        ContentItem.organisation_id == current_user.organisation_id,
        (ContentVersion.id == review_id) | (ContentVersion.review_job_id == str(review_id)),
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Review not found")
    version_id = version.id
    organisation_id = current_user.organisation_id
    try:
        last_event_id = max(0, int(request.headers.get("Last-Event-ID", "0")))
    except ValueError:
        last_event_id = 0

    def generate():
        cursor = last_event_id
        last_heartbeat = time.monotonic()
        while True:
            with SessionLocal() as stream_db:
                events = stream_db.query(ReviewEvent).filter(
                    ReviewEvent.content_version_id == version_id,
                    ReviewEvent.organisation_id == organisation_id,
                    ReviewEvent.id > cursor,
                ).order_by(ReviewEvent.id.asc()).limit(100).all()
                terminal = False
                for event in events:
                    payload = {
                        "id": str(version.review_job_id or version_id),
                        "status": event.status,
                        "stage": event.stage,
                        "message": event.message,
                        "findings": event.findings or [],
                        "metadata": event.metadata_json or {},
                    }
                    cursor = event.id
                    yield f"id: {event.id}\nevent: review\ndata: {json.dumps(payload)}\n\n"
                    if is_terminal_review_status(event.status):
                        terminal = True
                if terminal:
                    return
                state = stream_db.query(ContentVersion.review_job_status).filter(
                    ContentVersion.id == version_id
                ).scalar()
                if state in {"completed", "failed"} and not events:
                    return
            now = time.monotonic()
            if now - last_heartbeat >= 15:
                yield ": keep-alive\n\n"
                last_heartbeat = now
            time.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_router.post("/content/{content_id}/submit")
def submit_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["creator", "admin"])),
):
    content = _content_or_404(db, content_id, current_user)
    if current_user.role != "admin" and content.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the content creator can submit this item")
    version = _latest_version(db, content)
    if content.status == "needs_recheck" or version.status != "reviewed":
        raise HTTPException(status_code=409, detail="Run and complete a review before submitting this version")
    findings = db.query(Finding).filter(Finding.content_version_id == version.id).all()
    if any((row.severity == "high" or row.status == "cannot_verify") and not db.query(FindingDecision.id).filter(
        FindingDecision.finding_id == row.id
    ).first() for row in findings):
        raise HTTPException(status_code=409, detail="Resolve all high-risk and unverifiable findings before submitting")
    transition_content_status(db, content, "in_review", str(current_user.id), str(current_user.organisation_id))
    db.commit()
    db.refresh(content)
    return content


@api_router.post("/content/{content_id}/approve")
def approve_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["reviewer", "manager", "admin"])),
):
    content = _content_or_404(db, content_id, current_user)
    version = _latest_version(db, content)
    findings = db.query(Finding).filter(Finding.content_version_id == version.id).all()
    undecided_risks = []
    for finding in findings:
        is_risky = finding.severity == "high" or finding.status == "cannot_verify"
        latest = db.query(FindingDecision).filter(
            FindingDecision.finding_id == finding.id
        ).order_by(FindingDecision.created_at.desc()).first()
        if is_risky and not latest:
            undecided_risks.append(finding)
    if undecided_risks:
        raise HTTPException(
            status_code=409,
            detail="Resolve all high-severity and unverifiable findings before approval.",
        )
    if current_user.role == "manager" and any(
        finding.category == "claim" or finding.status == "cannot_verify"
        for finding in findings
    ):
        raise HTTPException(
            status_code=403,
            detail="A named reviewer must approve content containing claims or unverifiable findings.",
        )
    transition_content_status(db, content, "approved", str(current_user.id), str(current_user.organisation_id))
    db.commit()
    db.refresh(content)
    return content


@api_router.post("/content/{content_id}/request-changes")
def request_changes_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["reviewer", "manager", "admin"])),
):
    content = _content_or_404(db, content_id, current_user)
    transition_content_status(db, content, "changes_requested", str(current_user.id), str(current_user.organisation_id))
    db.commit()
    db.refresh(content)
    return content


@api_router.get("/queue")
def get_review_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["reviewer", "manager", "admin"])),
):
    return db.query(ContentItem).filter(
        ContentItem.organisation_id == current_user.organisation_id,
        ContentItem.status.in_(["in_review", "needs_recheck"]),
    ).order_by(ContentItem.created_at.asc()).all()


@api_router.post("/findings/{finding_id}/decision")
def record_finding_decision(
    finding_id: UUID,
    payload: FindingDecisionCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"creator", "reviewer", "manager", "admin"}:
        raise HTTPException(status_code=403, detail="Role cannot record finding decisions")
    if payload.action not in {"accept", "edit", "dismiss"}:
        raise HTTPException(status_code=422, detail="Action must be accept, edit, or dismiss")
    if payload.action == "dismiss" and not (payload.reason or "").strip():
        raise HTTPException(status_code=422, detail="A reason is required to dismiss a finding")
    if payload.action == "edit" and not (payload.edited_text or "").strip():
        raise HTTPException(status_code=422, detail="Edited text is required for an edit decision")
    finding = db.query(Finding).join(ContentVersion).join(ContentItem).filter(
        Finding.id == finding_id,
        ContentItem.organisation_id == current_user.organisation_id,
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    content = finding.content_version.content_item
    if current_user.role == "creator" and content.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the content creator can decide on this finding")
    decision = FindingDecision(
        finding_id=finding_id,
        user_id=current_user.id,
        action=payload.action,
        reason=payload.reason,
        edited_text=payload.edited_text,
    )
    db.add(decision)
    log_audit(
        db,
        str(current_user.organisation_id),
        f"FINDING_DECISION_{payload.action.upper()}",
        "finding",
        str(current_user.id),
        str(finding_id),
    )
    db.commit()
    db.refresh(decision)
    return decision


@api_router.get("/content/{content_id}/comments")
def get_comments(content_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _content_or_404(db, content_id, current_user)
    return db.query(Comment).filter(Comment.content_id == content_id).order_by(Comment.created_at.asc()).all()


@api_router.post("/content/{content_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(
    content_id: UUID,
    payload: CommentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _content_or_404(db, content_id, current_user)
    if payload.span_start < 0 or payload.span_end < payload.span_start:
        raise HTTPException(status_code=422, detail="Comment span must be a non-negative range")
    comment = Comment(
        content_id=content_id,
        user_id=current_user.id,
        span_start=payload.span_start,
        span_end=payload.span_end,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@api_router.get("/content/{content_id}/audit")
def get_audit_trail(content_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _content_or_404(db, content_id, current_user)
    return db.query(AuditLog).filter(
        AuditLog.organisation_id == current_user.organisation_id,
        AuditLog.entity_id == content_id,
    ).order_by(AuditLog.created_at.desc()).all()


@api_router.get("/alerts/fact-drift")
def get_fact_drift_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["reviewer", "manager", "admin"])),
):
    expired_fact_ids = db.query(Fact.id).filter(
        Fact.organisation_id == current_user.organisation_id,
        Fact.status == "approved",
        Fact.expires_at.is_not(None),
        Fact.expires_at <= datetime.utcnow(),
    ).all()
    for (fact_id,) in expired_fact_ids:
        trigger_fact_drift_alerts(db, str(fact_id), str(current_user.organisation_id))
    if expired_fact_ids:
        db.commit()
    rows = db.query(Alert).filter(
        Alert.organisation_id == current_user.organisation_id,
        Alert.alert_type == "fact_drift",
        Alert.status == "active",
    ).order_by(Alert.created_at.desc()).all()
    return [
        {
            "id": str(row.id),
            "ref_id": str(row.ref_id),
            "status": row.status,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@api_router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: UUID,
    payload: dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["reviewer", "manager", "admin"])),
):
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.organisation_id == current_user.organisation_id,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    next_status = payload.get("status")
    if next_status not in {"resolved", "dismissed"}:
        raise HTTPException(status_code=422, detail="Alert status must be resolved or dismissed")
    if alert.alert_type == "fact_drift" and next_status in {"resolved", "dismissed"}:
        content = db.query(ContentItem).filter(
            ContentItem.id == alert.ref_id,
            ContentItem.organisation_id == current_user.organisation_id,
        ).first()
        if content and content.status == "needs_recheck":
            version = _latest_version(db, content)
            if version.status != "reviewed":
                raise HTTPException(status_code=409, detail="Re-run the review before resolving this fact-drift alert")
            other_active = db.query(Alert.id).filter(
                Alert.organisation_id == current_user.organisation_id,
                Alert.alert_type == "fact_drift",
                Alert.ref_id == content.id,
                Alert.status == "active",
                Alert.id != alert.id,
            ).first()
            if not other_active:
                content.status = alert.prior_status if alert.prior_status in {"draft", "changes_requested"} else "in_review"
    alert.status = next_status
    db.commit()
    db.refresh(alert)
    return alert


@api_router.get("/insights/guideline-health")
def get_guideline_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    decisions = db.query(FindingDecision, Finding, Rule).join(
        Finding, FindingDecision.finding_id == Finding.id
    ).join(
        ContentVersion, Finding.content_version_id == ContentVersion.id
    ).join(
        ContentItem, ContentVersion.content_id == ContentItem.id
    ).join(
        Rule, Finding.source_id == Rule.id
    ).filter(
        ContentItem.organisation_id == current_user.organisation_id,
    ).all()
    metrics = calculate_guideline_health([
        {
            "id": str(decision.id),
            "rule_id": str(rule.id),
            "action": decision.action,
            "reason": decision.reason,
        }
        for decision, _, rule in decisions
    ])
    by_id = {item["rule_id"]: item for item in metrics["items"]}
    rules = db.query(Rule).filter(Rule.organisation_id == current_user.organisation_id).all()
    return [
        {
            "rule_id": str(rule.id),
            "clause_number": rule.clause_number,
            "text": rule.text,
            "category": rule.category,
            "dismiss_rate": by_id.get(str(rule.id), {}).get("dismiss_rate", 0.0),
            "total_decisions": by_id.get(str(rule.id), {}).get("decision_count", 0),
            "status": "unclear" if by_id.get(str(rule.id), {}).get("false_positive_flag") else "healthy",
        }
        for rule in rules
    ]


@api_router.post("/insights/guideline-health/{rule_id}/clarification", status_code=status.HTTP_201_CREATED)
def create_clarification(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    rule = db.query(Rule).filter(
        Rule.id == rule_id,
        Rule.organisation_id == current_user.organisation_id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rows = db.query(FindingDecision, Finding, ContentItem).join(
        Finding, FindingDecision.finding_id == Finding.id
    ).join(
        ContentVersion, Finding.content_version_id == ContentVersion.id
    ).join(
        ContentItem, ContentVersion.content_id == ContentItem.id
    ).filter(
        Finding.source_id == rule.id,
        ContentItem.organisation_id == current_user.organisation_id,
    ).all()
    draft = draft_rule_clarification(
        {"id": str(rule.id), "text": rule.text},
        [{
            "id": str(decision.id),
            "action": decision.action,
            "reason": decision.reason,
            "finding_id": str(finding.id),
            "content_id": str(content.id),
        } for decision, finding, content in rows],
    )
    clarification = RuleClarification(rule_id=rule.id, drafted_text=draft["drafted_text"], status="draft")
    db.add(clarification)
    db.flush()
    log_audit(
        db,
        str(current_user.organisation_id),
        "DRAFT_RULE_CLARIFICATION",
        "rule_clarification",
        str(current_user.id),
        str(clarification.id),
    )
    db.commit()
    db.refresh(clarification)
    return {
        "id": str(clarification.id),
        **draft,
    }


@api_router.patch("/insights/clarifications/{clarification_id}")
def update_clarification(
    clarification_id: UUID,
    payload: ClarificationUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    if payload.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Clarification status must be approved or rejected")
    clarification = db.query(RuleClarification).join(Rule).filter(
        RuleClarification.id == clarification_id,
        Rule.organisation_id == current_user.organisation_id,
    ).first()
    if not clarification:
        raise HTTPException(status_code=404, detail="Clarification not found")
    if clarification.status != "draft":
        raise HTTPException(status_code=409, detail="Clarification has already been reviewed")
    if payload.status == "approved":
        rule = db.query(Rule).filter(Rule.id == clarification.rule_id).first()
        rule.text = clarification.drafted_text
        rule.version += 1
    clarification.status = payload.status
    log_audit(
        db,
        str(current_user.organisation_id),
        f"RULE_CLARIFICATION_{payload.status.upper()}",
        "rule_clarification",
        str(current_user.id),
        str(clarification.id),
    )
    db.commit()
    db.refresh(clarification)
    return clarification


def _trust_result(db: Session, organisation_id: UUID) -> dict[str, Any]:
    dataset_path = Path(__file__).resolve().parents[1] / "eval" / "eval" / "labelled_samples.json"
    if not dataset_path.is_file():
        raise HTTPException(status_code=503, detail="The labelled evaluation dataset is unavailable")
    raw_samples = json.loads(dataset_path.read_text(encoding="utf-8"))
    rules = []
    for rule in db.query(Rule).filter(Rule.organisation_id == organisation_id, Rule.status == "approved"):
        rules.append({
            "id": str(rule.id),
            "source_type": "rule",
            "text": rule.text,
            "category": rule.category,
            "channels": rule.channels or ["all"],
            "status": rule.status,
            "type": rule.type,
            "config": rule.config or {},
        })
    facts = [
        {
            "id": str(fact.id),
            "source_type": "fact",
            "text": fact.text,
            "status": fact.status,
            "expires_at": fact.expires_at.isoformat() if fact.expires_at else None,
        }
        for fact in db.query(Fact).filter(Fact.organisation_id == organisation_id)
    ]

    def run_sample(sample):
        result = review_text(
            sample["content"],
            sample.get("intent", ""),
            rules,
            facts,
            content_id=str(sample.get("sample_id") or sample.get("id") or "evaluation"),
            channel=sample.get("channel"),
        )
        result["trace"] = {
            "retrieved_source_ids": result.get("retrieved_source_ids", []),
            "finding_stages": [
                {
                    "category": item.category if hasattr(item, "category") else item.get("category"),
                    "check_type": item.check_type if hasattr(item, "check_type") else item.get("check_type"),
                    "confidence": item.confidence if hasattr(item, "confidence") else item.get("confidence"),
                }
                for item in result.get("findings", [])
            ],
        }
        return result

    samples = [
        {
            **sample,
            "expected_issues": sample.get("expected_issues", sample.get("expected_findings", [])),
        }
        for sample in raw_samples
    ]
    return evaluate_dataset(samples, run_sample)


@api_router.get("/trust/scorecard")
def get_trust_scorecard(db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "manager"]))):
    result = _trust_result(db, current_user.organisation_id)
    return {
        "latest": result,
        "precision": result["precision"],
        "recall": result["recall"],
        "f1_score": result["f1"],
        "eval_samples_tested": result["sample_count"],
        "traces": result["traces"],
    }


@api_router.post("/trust/run")
def run_trust_scorecard(db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "manager"]))):
    return _trust_result(db, current_user.organisation_id)


@api_router.get("/insights/overview")
def get_insights_overview(db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "manager"]))):
    items = db.query(ContentItem).filter(ContentItem.organisation_id == current_user.organisation_id).all()
    versions = db.query(ContentVersion).join(ContentItem).filter(
        ContentItem.organisation_id == current_user.organisation_id
    ).all()
    version_ids = [version.id for version in versions]
    findings = db.query(Finding).filter(Finding.content_version_id.in_(version_ids)).all() if version_ids else []
    usage_count = db.query(AIUsageLog).filter(
        AIUsageLog.organisation_id == current_user.organisation_id
    ).count()
    now = datetime.now(timezone.utc)
    expiring = db.query(Fact).filter(
        Fact.organisation_id == current_user.organisation_id,
        Fact.expires_at.is_not(None),
        Fact.expires_at <= now + timedelta(days=30),
        Fact.expires_at > now,
    ).count()
    statuses = Counter(content.status for content in items)
    severities = Counter(finding.severity for finding in findings)
    decisions = db.query(FindingDecision).join(Finding).join(ContentVersion).join(ContentItem).filter(
        ContentItem.organisation_id == current_user.organisation_id
    ).all()
    decision_counts = Counter(row.action for row in decisions)
    return {
        "content_by_status": dict(statuses),
        "findings_by_severity": dict(severities),
        "unsupported_claims_flagged": sum(1 for finding in findings if finding.category == "claim"),
        "reviews_run": sum(1 for version in versions if version.status == "reviewed"),
        "avg_review_latency_ms": None,
        "degraded_reviews": 0,
        "human_decisions": dict(decision_counts),
        "facts_expiring_30d": expiring,
        "ai_usage_log_entries": usage_count,
    }
