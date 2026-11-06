import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db import Base

class Organisation(Base):
    __tablename__ = "organisations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organisation")
    guidelines = relationship("GuidelineDoc", back_populates="organisation")
    facts = relationship("Fact", back_populates="organisation")
    terms = relationship("Term", back_populates="organisation")
    assets = relationship("Asset", back_populates="organisation")
    content_items = relationship("ContentItem", back_populates="organisation")

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    organisation = relationship("Organisation", back_populates="users")

class GuidelineDoc(Base):
    __tablename__ = "guideline_docs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organisation = relationship("Organisation", back_populates="guidelines")
    rules = relationship("Rule", back_populates="guideline")

class Rule(Base):
    __tablename__ = "rules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    guideline_id = Column(UUID(as_uuid=True), ForeignKey("guideline_docs.id"), nullable=True)
    clause_number = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    channels = Column(ARRAY(String), default=[])
    status = Column(String, default="pending")
    version = Column(Integer, default=1)
    sensitivity = Column(String, default="normal")
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    guideline = relationship("GuidelineDoc", back_populates="rules")

class Fact(Base):
    __tablename__ = "facts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    text = Column(Text, nullable=False)
    owner = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1)
    status = Column(String, default="approved")
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organisation = relationship("Organisation", back_populates="facts")

class Term(Base):
    __tablename__ = "terms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    preferred = Column(String, nullable=False)
    banned = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organisation = relationship("Organisation", back_populates="terms")

class Asset(Base):
    __tablename__ = "assets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    name = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organisation = relationship("Organisation", back_populates="assets")

class ContentItem(Base):
    __tablename__ = "content_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)
    current_version_no = Column(Integer, default=1)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)

    organisation = relationship("Organisation", back_populates="content_items")
    versions = relationship("ContentVersion", back_populates="content_item", cascade="all, delete-orphan")

class ContentVersion(Base):
    __tablename__ = "content_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False)
    version_no = Column(Integer, nullable=False)
    body = Column(Text, nullable=False)
    intent = Column(String, nullable=False)
    channel = Column(String, default="general")
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)

    content_item = relationship("ContentItem", back_populates="versions")
    findings = relationship("Finding", back_populates="content_version", cascade="all, delete-orphan")

class Finding(Base):
    __tablename__ = "findings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_version_id = Column(UUID(as_uuid=True), ForeignKey("content_versions.id"), nullable=False)
    span_start = Column(Integer, default=0)
    span_end = Column(Integer, default=0)
    category = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    check_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    source_type = Column(String, nullable=True)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    explanation = Column(Text, nullable=False)
    suggestion_text = Column(Text, nullable=True)
    intent_preserved = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    content_version = relationship("ContentVersion", back_populates="findings")
    decisions = relationship("FindingDecision", back_populates="finding", cascade="all, delete-orphan")

class FindingDecision(Base):
    __tablename__ = "finding_decisions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    finding = relationship("Finding", back_populates="decisions")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    span_start = Column(Integer, default=0)
    span_end = Column(Integer, default=0)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AIUsageLog(Base):
    __tablename__ = "ai_usage_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    service = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    redacted_bool = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FactUsage(Base):
    __tablename__ = "fact_usage"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_version_id = Column(UUID(as_uuid=True), ForeignKey("content_versions.id"), nullable=False)
    fact_id = Column(UUID(as_uuid=True), ForeignKey("facts.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    content_version = relationship("ContentVersion")
    fact = relationship("Fact")

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id = Column(UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False)
    alert_type = Column(String, nullable=False)
    ref_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

class RuleClarification(Base):
    __tablename__ = "rule_clarifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("rules.id"), nullable=False)
    drafted_text = Column(Text, nullable=False)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
