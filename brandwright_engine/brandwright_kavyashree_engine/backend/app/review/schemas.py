from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class TextSpan:
    start: int
    end: int
    page: int | None = None

@dataclass
class Finding:
    id: str
    content_id: str
    version_no: int
    span: TextSpan
    category: str
    severity: str
    check_type: str
    status: str
    confidence: float
    source: dict[str, Any] | None
    explanation: str
    suggestion: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    trace: dict[str, Any] | None = None

    def to_dict(self):
        result = asdict(self)
        result["span"] = asdict(self.span)
        return result
