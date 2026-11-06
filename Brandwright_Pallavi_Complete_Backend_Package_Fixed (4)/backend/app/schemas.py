from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class TokenSchema(BaseModel):
    access_token: str
    token_type: str

class LoginSchema(BaseModel):
    email: str
    password: str

class UserSchema(BaseModel):
    id: UUID
    email: str
    role: str
    organisation_id: UUID
    class Config:
        from_attributes = True

class RuleCreateSchema(BaseModel):
    clause_number: str
    text: str
    category: str
    channels: Optional[List[str]] = []

class RuleSchema(RuleCreateSchema):
    id: UUID
    status: str
    version: int
    created_at: datetime
    class Config:
        from_attributes = True

class FactCreateSchema(BaseModel):
    text: str
    owner: Optional[str] = None
    source_url: Optional[str] = None
    expires_at: Optional[datetime] = None

class FactSchema(FactCreateSchema):
    id: UUID
    version: int
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

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
    class Config:
        from_attributes = True

class FindingDecisionCreateSchema(BaseModel):
    action: str
    reason: Optional[str] = None
