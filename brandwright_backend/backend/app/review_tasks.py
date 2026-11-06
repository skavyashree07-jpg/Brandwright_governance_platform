import re
from typing import List, Dict, Any

def redact_sensitive_data(text: str) -> str:
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    phone_pattern = r'(?:\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
    
    redacted = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
    redacted = re.sub(phone_pattern, "[REDACTED_PHONE]", redacted)
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
