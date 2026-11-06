import re, uuid
from datetime import datetime, timezone
from .schemas import Finding, TextSpan

PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|x|times|days?|hours?|years?)\b", re.I),
    re.compile(r"\b(?:guaranteed|always|never|zero risk|safest|best|number one)\b", re.I),
    re.compile(r"\b(?:more|less|faster|longer|better) than\b", re.I),
]

def extract_claims(text):
    found = {}
    for pattern in PATTERNS:
        for m in pattern.finditer(text): found[(m.start(), m.end())] = m.group()
    return [{"text": value, "start": a, "end": b} for (a,b), value in sorted(found.items())]

def verify_claims(text, facts, content_id="demo-content", version_no=1, now=None):
    now = now or datetime.now(timezone.utc)
    findings, usage = [], []
    approved = [f for f in facts if f.get("status", "approved") == "approved"]
    for claim in extract_claims(text):
        claim_tokens = set(re.findall(r"[a-z0-9%]+", claim["text"].casefold()))
        matched = next((f for f in approved if claim_tokens and
            claim_tokens.issubset(set(re.findall(r"[a-z0-9%]+", f.get("text","").casefold())))), None)
        expired = False
        if matched and matched.get("expires_at"):
            expiry = matched["expires_at"]
            if isinstance(expiry, str): expiry = datetime.fromisoformat(expiry.replace("Z","+00:00"))
            if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
            expired = expiry <= now
        if matched and not expired:
            usage.append({"fact_id": str(matched["id"]), "content_id": content_id, "version_no": version_no})
            continue
        sid = str(matched["id"]) if matched else None
        findings.append(Finding(str(uuid.uuid4()), content_id, version_no,
            TextSpan(claim["start"], claim["end"]), "claim", "high", "retrieval_ai",
            "cannot_verify", 0.95 if expired else 0.65,
            {"type":"fact","id":sid,"clause_text":matched.get("text","")} if matched else None,
            "The closest approved fact has expired; human verification is required." if expired
            else "No approved fact was found that substantiates this claim.",
            trace={"stage":"claims_ledger","confidence":0.95 if expired else 0.65,
                   "retrieved_source_ids":[sid] if sid else []}))
    return findings, usage
