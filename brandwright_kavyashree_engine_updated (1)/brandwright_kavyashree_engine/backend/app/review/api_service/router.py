from datetime import datetime, timezone
from pathlib import Path
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ingestion import extract_file
from ..brandbook import parse_brand_book
from ..visual_checks import inspect_image
from ..pipeline import review_text
from ...trust.evaluator import evaluate_dataset
from ...insights.guideline_drafting import draft_rule_clarification, calculate_guideline_health
from .config import get_settings
from .database import get_db
from .models import (EngineDocument, EngineReview, EngineFinding, EngineFactUsage,
                     EngineTrustRun, EngineClarification, EngineFindingDecision, EngineAIUsage)
from .schemas import (ReviewRequest, DocumentReviewRequest, TrustRunRequest,
                      ClarificationRequest, FindingDecisionRequest)

router = APIRouter(prefix="/api/engine", tags=["AI & Review Engine"])
ALLOWED_SUFFIXES = {".txt", ".md", ".csv", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _run(content: str, intent: str, rules, facts, content_id: str, version_no: int,
         local_only: bool, confidential_strings: list[str]):
    return review_text(content, intent, rules, facts, content_id=content_id,
                       version_no=version_no, local_only=local_only,
                       confidential_strings=confidential_strings)


def _persist_review(db: Session, result: dict, intent: str, content_id: str,
                    version_no: int, document_id: str | None = None) -> EngineReview:
    review_id = str(uuid4())
    serial_result = {**result, "findings": [x.to_dict() if hasattr(x, "to_dict") else x for x in result["findings"]]}
    row = EngineReview(id=review_id, document_id=document_id, content_id=content_id,
                       version_no=version_no, intent=intent, status="completed", result=serial_result)
    for item in serial_result["findings"]:
        finding = item.to_dict() if hasattr(item, "to_dict") else item
        row.findings.append(EngineFinding(
            id=str(finding.get("id") or uuid4()), category=str(finding.get("category", "unknown")),
            severity=str(finding.get("severity", "info")), check_type=str(finding.get("check_type", "unknown")),
            confidence=float(finding.get("confidence", 0)), payload=finding))
    db.add(row)
    db.flush()
    for item in result.get("fact_usage", []):
        row_id = f"{uuid4()}"
        db.add(EngineFactUsage(id=row_id, review_id=review_id,
                               fact_id=str(item.get("fact_id") or item.get("id") or "unknown"), payload=item))
    for item in result.get("ai_usage", []):
        db.add(EngineAIUsage(id=str(uuid4()), review_id=review_id,
            service=item.get("service", "unknown"), purpose=item.get("purpose", "review"),
            model=item.get("model"), external=bool(item.get("external")),
            redacted=bool(item.get("redacted")), redaction_counts=item.get("redaction_counts", {}),
            input_chars=int(item.get("input_chars", 0)), output_chars=int(item.get("output_chars", 0)),
            error=item.get("error"), blocked=bool(item.get("blocked"))))
    db.commit()
    db.refresh(row)
    return row


def _review_response(row: EngineReview):
    return {"id": row.id, "document_id": row.document_id, "content_id": row.content_id,
            "version_no": row.version_no, "intent": row.intent, "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "result": row.result,
            "findings": [f.payload for f in row.findings]}


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Extract text and positions from a supported source document; source file bytes are not retained."""
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, f"Unsupported file type: {suffix or 'unknown'}")
    data = await file.read()
    limit = get_settings().max_upload_bytes
    if len(data) > limit:
        raise HTTPException(413, f"File exceeds the {limit}-byte upload limit")
    try:
        extraction = extract_file(data, filename)
    except ImportError as exc:
        raise HTTPException(503, f"A parser dependency is not installed: {exc.name}") from exc
    except Exception as exc:
        raise HTTPException(422, f"Could not extract document: {exc}") from exc
    if not extraction.text.strip():
        raise HTTPException(422, "No text could be extracted from this file")
    document_id = str(uuid4())
    payload = extraction.to_dict()
    row = EngineDocument(id=document_id, filename=filename, media_type=extraction.media_type,
                         extracted_text=extraction.text, extraction=payload)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "filename": row.filename, "media_type": row.media_type,
            "text": row.extracted_text, "segments": payload["segments"], "warnings": payload["warnings"],
            "created_at": row.created_at.isoformat() if row.created_at else None}


@router.post("/reviews", status_code=status.HTTP_201_CREATED)
def create_review(body: ReviewRequest, db: Session = Depends(get_db)):
    result = _run(body.content, body.intent, [x.model_dump() for x in body.rules],
                  [x.model_dump() for x in body.facts], body.content_id, body.version_no,
                  body.local_only, body.confidential_strings)
    row = _persist_review(db, result, body.intent, body.content_id, body.version_no)
    return _review_response(row)


@router.post("/documents/{document_id}/review", status_code=status.HTTP_201_CREATED)
def review_document(document_id: str, body: DocumentReviewRequest, db: Session = Depends(get_db)):
    document = db.get(EngineDocument, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    result = _run(document.extracted_text, body.intent, [x.model_dump() for x in body.rules],
                  [x.model_dump() for x in body.facts], body.content_id, body.version_no,
                  body.local_only, body.confidential_strings)
    row = _persist_review(db, result, body.intent, body.content_id, body.version_no, document_id)
    return _review_response(row)


@router.get("/reviews")
def list_reviews(limit: int = 25, db: Session = Depends(get_db)):
    if not 1 <= limit <= 100:
        raise HTTPException(422, "limit must be between 1 and 100")
    rows = db.scalars(select(EngineReview).order_by(EngineReview.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": r.id, "content_id": r.content_id, "version_no": r.version_no,
                        "status": r.status, "finding_count": len(r.findings),
                        "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]}


@router.get("/reviews/{review_id}")
def get_review(review_id: str, db: Session = Depends(get_db)):
    row = db.get(EngineReview, review_id)
    if not row:
        raise HTTPException(404, "Review not found")
    return _review_response(row)


@router.get("/reviews/{review_id}/fact-usage")
def get_fact_usage(review_id: str, db: Session = Depends(get_db)):
    if not db.get(EngineReview, review_id):
        raise HTTPException(404, "Review not found")
    rows = db.scalars(select(EngineFactUsage).where(EngineFactUsage.review_id == review_id)).all()
    return {"review_id": review_id, "items": [r.payload for r in rows]}


def _bundled_demo_samples():
    dataset_path = Path(__file__).resolve().parents[4] / "eval" / "demo_samples.json"
    if not dataset_path.is_file():
        raise HTTPException(503, "No bundled evaluation dataset is available; supply samples in the request")
    return json.loads(dataset_path.read_text(encoding="utf-8"))


@router.get("/reviews/{review_id}/ai-usage")
def get_ai_usage(review_id: str, db: Session = Depends(get_db)):
    if not db.get(EngineReview, review_id):
        raise HTTPException(404, "Review not found")
    rows = db.scalars(select(EngineAIUsage).where(EngineAIUsage.review_id == review_id).order_by(EngineAIUsage.created_at.asc())).all()
    return {"review_id": review_id, "items": [{
        "service": row.service, "purpose": row.purpose, "model": row.model,
        "external": row.external, "redacted": row.redacted,
        "redaction_counts": row.redaction_counts, "input_chars": row.input_chars,
        "output_chars": row.output_chars, "error": row.error, "blocked": row.blocked,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]}


@router.post("/trust/run", status_code=status.HTTP_201_CREATED)
def run_trust(body: TrustRunRequest | None = None, db: Session = Depends(get_db)):
    samples = [s.model_dump() for s in body.samples] if body else _bundled_demo_samples()
    dataset_source = "request" if body else "bundled_fictional_demo"
    def pipeline(sample):
        result = _run(sample["content"], sample["intent"], sample["rules"], sample["facts"],
                      sample["id"], 1, True, [])
        return {"findings": result["findings"], "trace": {
            "retrieved_source_ids": result.get("retrieved_source_ids", []),
            "ai_services_used": result.get("ai_services_used", []),
            "local_only": result.get("local_only", True),
            "redaction_count": len(result.get("redactions", [])),
        }}
    result = evaluate_dataset(samples, pipeline)
    run_id = str(uuid4())
    result["run_id"] = run_id
    result["dataset_source"] = dataset_source
    result["benchmark_warning"] = ("Fictional smoke-test dataset only; do not treat these metrics as production accuracy."
                                   if dataset_source == "bundled_fictional_demo" else None)
    db.add(EngineTrustRun(id=run_id, result=result)); db.commit()
    return result


@router.get("/trust/scorecard")
def get_scorecard(db: Session = Depends(get_db)):
    rows = db.scalars(select(EngineTrustRun).order_by(EngineTrustRun.created_at.desc()).limit(50)).all()
    history = [r.result for r in rows]
    return {"latest": history[0] if history else None, "history": history}


@router.post("/guidelines/parse")
def parse_guideline(body: dict):
    text = body.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(422, "text is required")
    rules = parse_brand_book(text)
    return {"rules": rules, "count": len(rules), "status": "draft",
            "requires_owner_approval": True}


@router.post("/images/review")
async def review_image(file: UploadFile = File(...), alt_text: str | None = Form(None),
                       allowed_palette: str | None = Form(None),
                       palette_tolerance: int = Form(55),
                       logo_bbox: str | None = Form(None),
                       min_logo_width: int = Form(0), min_logo_height: int = Form(0),
                       foreground: str | None = Form(None), background: str | None = Form(None),
                       min_contrast: float = Form(4.5)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        raise HTTPException(415, "Image review accepts PNG, JPG, TIFF, BMP or WEBP")
    data = await file.read()
    if len(data) > get_settings().max_upload_bytes:
        raise HTTPException(413, "Image exceeds the upload size limit")
    palette = [x.strip() for x in allowed_palette.split(",") if x.strip()] if allowed_palette else None
    bbox = None
    if logo_bbox:
        try: bbox = [int(x.strip()) for x in logo_bbox.split(",")]
        except ValueError as exc: raise HTTPException(422, "logo_bbox must be x,y,width,height") from exc
    try:
        return inspect_image(data, alt_text=alt_text, allowed_palette=palette,
            palette_tolerance=palette_tolerance, logo_bbox=bbox, min_logo_width=min_logo_width,
            min_logo_height=min_logo_height, foreground=foreground, background=background,
            min_contrast=min_contrast)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, f"Image checks could not run: {exc}") from exc


@router.post("/findings/{finding_id}/decision", status_code=status.HTTP_201_CREATED)
def record_finding_decision(finding_id: str, body: FindingDecisionRequest, db: Session = Depends(get_db)):
    finding = db.get(EngineFinding, finding_id)
    if not finding:
        raise HTTPException(404, "Finding not found")
    source = (finding.payload or {}).get("source") or {}
    if source.get("id") and str(source.get("id")) != body.rule_id:
        raise HTTPException(422, "rule_id does not match the finding's cited source")
    if body.action == "dismiss" and not body.reason.strip():
        raise HTTPException(422, "A dismissal requires a reason")
    if body.action == "edit" and not (body.edited_text or "").strip():
        raise HTTPException(422, "An edit decision requires edited_text")
    row = EngineFindingDecision(
        id=str(uuid4()), finding_id=finding_id, rule_id=body.rule_id, action=body.action,
        reason=body.reason.strip(), edited_text=body.edited_text, actor_role=body.actor_role)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "finding_id": row.finding_id, "rule_id": row.rule_id,
            "action": row.action, "reason": row.reason, "edited_text": row.edited_text,
            "actor_role": row.actor_role, "created_at": row.created_at.isoformat() if row.created_at else None}


@router.get("/insights/guideline-health")
def get_guideline_health(min_decisions: int = 3, db: Session = Depends(get_db)):
    if not 1 <= min_decisions <= 100:
        raise HTTPException(422, "min_decisions must be between 1 and 100")
    rows = db.scalars(select(EngineFindingDecision).order_by(EngineFindingDecision.created_at.asc())).all()
    decisions = [{"id": row.id, "rule_id": row.rule_id, "action": row.action,
                  "reason": row.reason, "edited_text": row.edited_text,
                  "actor_role": row.actor_role,
                  "created_at": row.created_at.isoformat() if row.created_at else None}
                 for row in rows]
    return calculate_guideline_health(decisions, min_decisions=min_decisions)


@router.post("/guidelines/clarifications", status_code=status.HTTP_201_CREATED)
def create_clarification(body: ClarificationRequest, db: Session = Depends(get_db)):
    decisions = body.decisions
    if not decisions:
        rule_id = str(body.rule.get("id") or body.rule.get("rule_id") or "")
        rows = db.scalars(select(EngineFindingDecision).where(
            EngineFindingDecision.rule_id == rule_id).order_by(EngineFindingDecision.created_at.asc())).all()
        decisions = [{"id": row.id, "action": row.action, "reason": row.reason,
                      "finding_id": row.finding_id, "edited_text": row.edited_text,
                      "reviewer_role": row.actor_role,
                      "created_at": row.created_at.isoformat() if row.created_at else None}
                     for row in rows]
    try:
        draft = draft_rule_clarification(body.rule, decisions)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row = EngineClarification(id=str(uuid4()), rule_id=draft["rule_id"],
        current_text=draft["current_text"], drafted_text=draft["drafted_text"],
        motivating_decisions=draft["motivating_decisions"], evidence=draft["evidence"],
        status="draft", requires_owner_approval=True)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "rule_id": row.rule_id, "current_text": row.current_text,
            "drafted_text": row.drafted_text, "motivating_decisions": row.motivating_decisions,
            "evidence": row.evidence, "status": row.status,
            "requires_owner_approval": row.requires_owner_approval,
            "approval_note": "This is a proposal only; it does not change the active guideline."}


@router.get("/guidelines/clarifications")
def list_clarifications(db: Session = Depends(get_db)):
    rows = db.scalars(select(EngineClarification).order_by(EngineClarification.created_at.desc())).all()
    return {"items": [{"id": r.id, "rule_id": r.rule_id, "current_text": r.current_text,
        "drafted_text": r.drafted_text, "motivating_decisions": r.motivating_decisions,
        "evidence": r.evidence, "status": r.status,
        "requires_owner_approval": r.requires_owner_approval} for r in rows]}
