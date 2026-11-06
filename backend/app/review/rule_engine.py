import re, uuid
from .schemas import Finding, TextSpan

def _make(text, rule, start, end, category, explanation, suggestion=None):
    sid = str(rule["id"])
    return Finding(str(uuid.uuid4()), "demo-content", 1, TextSpan(start, end), category,
        rule.get("severity", "medium"), "rule", "violation", 1.0,
        {"type": "rule", "id": sid, "clause_text": rule.get("text", "")},
        explanation, {"text": suggestion, "intent_preserved": True} if suggestion else None,
        trace={"stage": "rule", "confidence": 1.0, "retrieved_source_ids": [sid]})

def run_rule_engine(text, rules, content_id="demo-content", version_no=1, channel=None):
    findings = []
    for rule in rules:
        if rule.get("status", "approved") != "approved": continue
        channels = {str(value).casefold() for value in (rule.get("channels") or ["all"])}
        if channel and "all" not in channels and channel.casefold() not in channels: continue
        cfg, kind = rule.get("config", {}), rule.get("type")
        if kind == "banned_term":
            term = cfg.get("term")
            if not term: continue
            for m in re.finditer(re.escape(term), text, re.I):
                findings.append(_make(text, rule, m.start(), m.end(), "terminology",
                    f"'{m.group()}' is not approved terminology. {rule.get('text','')}",
                    cfg.get("replacement")))
        elif kind == "preferred_term":
            for variant in cfg.get("variants", []):
                if not variant: continue
                for m in re.finditer(re.escape(variant), text, re.I):
                    findings.append(_make(text, rule, m.start(), m.end(), "terminology",
                        f"Use '{cfg.get('preferred')}' instead of '{m.group()}'.",
                        cfg.get("preferred")))
        elif kind == "required_disclaimer":
            phrase = cfg.get("phrase", "")
            if phrase and phrase.casefold() not in text.casefold():
                findings.append(_make(text, rule, 0, 0, "messaging",
                    f"Required disclaimer is missing: {phrase}."))
        elif kind == "superlative":
            for term in cfg.get("terms", ["best", "safest", "number one", "unmatched"]):
                for m in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I):
                    findings.append(_make(text, rule, m.start(), m.end(), "claim",
                        f"Superlative '{m.group()}' requires approved substantiation."))
    # Preserve caller identifiers/version.
    for f in findings:
        f.content_id, f.version_no = content_id, version_no
    return findings
