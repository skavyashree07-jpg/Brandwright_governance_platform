import re
from typing import Any, Dict, List


def redact_sensitive_data(text: str) -> str:
    if not text:
        return text

    patterns = [
        (r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[REDACTED_EMAIL]"),
        (r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})", "[REDACTED_PHONE]"),
        (r"\b(?:\d{4}[ -]?){2}\d{4}\b", "[REDACTED_ID]"),
        (r"\b(?:sk|pk|api|key)[_-][A-Za-z0-9_-]{12,}\b", "[REDACTED_KEY]"),
    ]

    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.I)
    return redacted

class MockLLMClient:
    def analyze_content(self, body: str, intent: str, rules: List[Dict], facts: List[Dict]) -> List[Dict[str, Any]]:
        redacted_body = redact_sensitive_data(body)
        findings = []
        
        if "Brandwright" not in redacted_body:
            rule_id = rules[0]["id"] if rules else None
            findings.append({
                "span": {"start": 0, "end": max(len(redacted_body), 1)},
                "category": "messaging",
                "severity": "high",
                "check_type": "rule",
                "status": "violation",
                "confidence": 0.95,
                "source": {"type": "rule", "id": str(rule_id), "clause_text": rules[0]["text"] if rules else "Include Brandwright"},
                "explanation": "Content does not explicitly mention the Brandwright brand name.",
                "suggestion": {"text": f"Brandwright: {body}", "intent_preserved": True}
            })
            
        return findings
