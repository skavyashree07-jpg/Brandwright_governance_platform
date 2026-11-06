from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Literal
from uuid import UUID
from datetime import datetime

class TokenSchema(BaseModel):
    access_token: str
    token_type: str

class LoginSchema(BaseModel):
    email: str
    password: str

class DemoLoginSchema(BaseModel):
    role: Literal["creator", "reviewer", "admin"]

class UserSchema(BaseModel):
    id: UUID
    email: str
    role: str
    organisation_id: UUID
    model_config = ConfigDict(from_attributes=True)

class RuleCreateSchema(BaseModel):
    clause_number: str
    text: str
    category: str
    channels: List[str] = Field(default_factory=list)
    type: Optional[str] = None
    config: dict = Field(default_factory=dict)

class RuleSchema(RuleCreateSchema):
    id: UUID
    status: str
    version: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FactCreateSchema(BaseModel):
    text: str
    owner: Optional[str] = None
    source_url: Optional[str] = None
    expires_at: Optional[datetime] = None

class FactUpdateSchema(BaseModel):
    text: Optional[str] = None
    owner: Optional[str] = None
    source_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    status: Optional[str] = None

class FactSchema(FactCreateSchema):
    id: UUID
    version: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ContentCreateSchema(BaseModel):
    title: str
    body: str
    intent: str
    channel: Optional[str] = "general"

class ContentItemSchema(BaseModel):
    id: UUID
    title: Optional[str]
    current_version_no: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FindingDecisionCreateSchema(BaseModel):
    action: str
    reason: Optional[str] = None
    edited_text: Optional[str] = None

class TermCreateSchema(BaseModel):
    preferred: str
    banned: str
    notes: Optional[str] = None

class AssetCreateSchema(BaseModel):
    name: str
    file_url: str
    metadata_json: Optional[str] = None

class ContentVersionCreateSchema(BaseModel):
    body: str
    intent: str
    channel: Optional[str] = None

class CommentCreateSchema(BaseModel):
    span_start: int = 0
    span_end: int = 0
    body: str

class ClarificationUpdateSchema(BaseModel):
    status: str
