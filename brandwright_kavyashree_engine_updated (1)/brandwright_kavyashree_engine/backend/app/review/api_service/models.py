from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class EngineDocument(Base):
    __tablename__ = "review_engine_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(120))
    extracted_text: Mapped[str] = mapped_column(Text)
    extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class EngineReview(Base):
    __tablename__ = "review_engine_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("review_engine_documents.id"), nullable=True)
    content_id: Mapped[str] = mapped_column(String(120), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    intent: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document: Mapped[EngineDocument | None] = relationship()
    findings: Mapped[list["EngineFinding"]] = relationship(back_populates="review", cascade="all, delete-orphan")

class EngineFinding(Base):
    __tablename__ = "review_engine_findings"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("review_engine_reviews.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(30))
    check_type: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    review: Mapped[EngineReview] = relationship(back_populates="findings")

class EngineFactUsage(Base):
    __tablename__ = "review_engine_fact_usage"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("review_engine_reviews.id", ondelete="CASCADE"), index=True)
    fact_id: Mapped[str] = mapped_column(String(120), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

class EngineTrustRun(Base):
    __tablename__ = "review_engine_trust_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class EngineClarification(Base):
    __tablename__ = "review_engine_clarifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(120), index=True)
    current_text: Mapped[str] = mapped_column(Text)
    drafted_text: Mapped[str] = mapped_column(Text)
    motivating_decisions: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    requires_owner_approval: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EngineFindingDecision(Base):
    __tablename__ = "review_engine_finding_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("review_engine_findings.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EngineAIUsage(Base):
    __tablename__ = "review_engine_ai_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("review_engine_reviews.id", ondelete="CASCADE"), index=True)
    service: Mapped[str] = mapped_column(String(100))
    purpose: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external: Mapped[bool] = mapped_column(default=False)
    redacted: Mapped[bool] = mapped_column(default=False)
    redaction_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    input_chars: Mapped[int] = mapped_column(Integer, default=0)
    output_chars: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
