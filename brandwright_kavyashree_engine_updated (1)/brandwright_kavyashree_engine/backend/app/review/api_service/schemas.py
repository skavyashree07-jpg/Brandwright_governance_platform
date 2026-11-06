from typing import Any
from pydantic import BaseModel, Field, ConfigDict

class RuleInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    text: str = ""
    type: str = "guideline"
    config: dict[str, Any] = Field(default_factory=dict)

class FactInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    text: str
    expires_at: str | None = None
    owner: str | None = None

class ReviewRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500_000)
    intent: str = Field(min_length=1, max_length=2_000)
    content_id: str = Field(default="submitted-content", max_length=120)
    version_no: int = Field(default=1, ge=1)
    rules: list[RuleInput] = Field(default_factory=list)
    facts: list[FactInput] = Field(default_factory=list)
    local_only: bool = True
    confidential_strings: list[str] = Field(default_factory=list)

class DocumentReviewRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=2_000)
    content_id: str = Field(default="uploaded-content", max_length=120)
    version_no: int = Field(default=1, ge=1)
    rules: list[RuleInput] = Field(default_factory=list)
    facts: list[FactInput] = Field(default_factory=list)
    local_only: bool = True
    confidential_strings: list[str] = Field(default_factory=list)

class TrustSample(BaseModel):
    id: str
    content: str
    intent: str = "Review this content against the supplied brand guidance."
    rules: list[RuleInput] = Field(default_factory=list)
    facts: list[FactInput] = Field(default_factory=list)
    expected_issues: list[Any] = Field(default_factory=list)

class TrustRunRequest(BaseModel):
    samples: list[TrustSample] = Field(min_length=1, max_length=500)

class ClarificationRequest(BaseModel):
    rule: dict[str, Any]
    decisions: list[dict[str, Any]] = Field(default_factory=list)


class FindingDecisionRequest(BaseModel):
    rule_id: str = Field(min_length=1, max_length=120)
    action: str = Field(pattern="^(accept|edit|dismiss)$")
    reason: str = Field(default="", max_length=4000)
    edited_text: str | None = Field(default=None, max_length=20000)
    actor_role: str | None = Field(default=None, pattern="^(creator|manager|reviewer|admin)$")
