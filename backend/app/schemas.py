from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List, Literal
from uuid import UUID
from datetime import datetime
from urllib.parse import urlsplit


class BrandCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=5000)
    industry: Optional[str] = Field(default=None, max_length=120)
    website_url: Optional[str] = Field(default=None, max_length=2048)
    primary_colour: Optional[str] = None
    secondary_colour: Optional[str] = None
    voice: Optional[str] = Field(default=None, max_length=120)
    target_audience: Optional[str] = Field(default=None, max_length=5000)
    mission: Optional[str] = Field(default=None, max_length=5000)
    vision: Optional[str] = Field(default=None, max_length=5000)
    guidelines: Optional[str] = Field(default=None, max_length=20000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Brand name cannot be empty.")
        return value

    @field_validator("website_url")
    @classmethod
    def validate_website_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Website URL must be a valid http or https URL.")
        return value

    @field_validator("primary_colour", "secondary_colour")
    @classmethod
    def validate_colour(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value:
            return value
        if len(value) != 7 or value[0] != "#" or any(char not in "0123456789abcdefABCDEF" for char in value[1:]):
            raise ValueError("Brand colours must use six-digit hex notation, for example #173F35.")
        return value.upper()

    model_config = ConfigDict(extra="forbid")


class BrandUpdateSchema(BrandCreateSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)


class BrandSchema(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    industry: Optional[str]
    website_url: Optional[str]
    logo_url: Optional[str]
    primary_colour: Optional[str]
    secondary_colour: Optional[str]
    voice: Optional[str]
    target_audience: Optional[str]
    mission: Optional[str]
    vision: Optional[str]
    guidelines: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

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
    jury_demo: bool = False
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
    brand_id: Optional[UUID] = None
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
    brand_id: Optional[UUID] = None
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



class TermSchema(BaseModel):
    id: UUID
    brand_id: Optional[UUID] = None
    preferred: str
    banned: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

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
