import re, uuid
from datetime import datetime, timezone
from .schemas import Finding, TextSpan

PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|x|times|days?|hours?|years?|months?)\b", re.I),
    re.compile(r"\b(?:guaranteed|always|never|zero risk|safest|best|number one|all|every|complete|completely)\b", re.I),
    re.compile(r"\b(?:more|less|faster|longer|better|stronger|higher|lower) than\b", re.I),
    re.compile(r"\b(?:up to|at least|at most|may|can|could|approximately|around|roughly)\b", re.I),
]

CLAIM_BROADENERS = (
    "guaranteed", "always", "never", "every", "all", "complete", "completely",
    "zero risk", "under every operating condition", "under any condition",
)
QUALIFIED_FACT_HINTS = (
    "up to", "at least", "at most", "approximately", "around", "roughly",
    "may", "can", "could", "perhaps", "under laboratory conditions", "under normal conditions",
)
ABSOLUTE_CLAIM_HINTS = (
    "guaranteed", "always", "never", "every", "all", "completely",
    "will", "certainly", "zero risk", "under every operating condition",
)


def _is_expired_fact(fact, now):
    expires_at = fact.get("expires_at")
    if not expires_at:
        return False
    expiry = expires_at
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= now


def _extract_numeric_values(text):
    return [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]


def _claim_extends_fact(claim_text, fact_text):
    claim_lower = claim_text.casefold()
    fact_lower = fact_text.casefold()

    if any(marker in claim_lower for marker in CLAIM_BROADENERS) and not any(marker in fact_lower for marker in CLAIM_BROADENERS):
        return True

    if any(marker in fact_lower for marker in QUALIFIED_FACT_HINTS) and any(marker in claim_lower for marker in ABSOLUTE_CLAIM_HINTS):
        return True

    if "up to" in fact_lower and any(marker in claim_lower for marker in ("guaranteed", "every", "all", "always", "never", "under every", "under any")):
        return True

    if "under laboratory conditions" in fact_lower and any(marker in claim_lower for marker in ("under every operating condition", "in every case", "always", "guaranteed")):
        return True

    if "may" in fact_lower and any(marker in claim_lower for marker in ("will", "guarantees", "always", "certainly")):
        return True

    fact_numbers = _extract_numeric_values(fact_lower)
    claim_numbers = _extract_numeric_values(claim_lower)
    if fact_numbers and claim_numbers:
        fact_max = max(fact_numbers)
        claim_max = max(claim_numbers)
        if claim_max > fact_max and not any(marker in claim_lower for marker in QUALIFIED_FACT_HINTS):
            return True

    return False


def extract_claims(text):
    found = {}
    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            found[(match.start(), match.end())] = match.group(0)
    return [{"text": value, "start": a, "end": b} for (a, b), value in sorted(found.items())]


def _best_fact_match(text, approved_facts):
    text_tokens = set(re.findall(r"[a-z0-9%]+", text.casefold()))
    ranked = []
    for fact in approved_facts:
        fact_text = str(fact.get("text", ""))
        fact_tokens = set(re.findall(r"[a-z0-9%]+", fact_text.casefold()))
        if not fact_tokens:
            continue
        overlap = len(text_tokens & fact_tokens)
        if overlap:
            ranked.append((overlap, fact))
    if not ranked:
        return None
    return max(ranked, key=lambda item: item[0])[1]


def verify_claims(text, facts, content_id="demo-content", version_no=1, now=None):
    now = now or datetime.now(timezone.utc)
    findings, usage = [], []
    approved = [fact for fact in facts if fact.get("status", "approved") == "approved"]

    if approved:
        fact_match = _best_fact_match(text, approved)
        if fact_match and _claim_extends_fact(text, str(fact_match.get("text", ""))):
            sid = str(fact_match["id"]) if fact_match.get("id") is not None else None
            findings.append(
                Finding(
                    str(uuid.uuid4()),
                    content_id,
                    version_no,
                    TextSpan(0, len(text)),
                    "claim",
                    "high",
                    "retrieval_ai",
                    "cannot_verify",
                    0.95,
                    {"type": "fact", "id": sid, "clause_text": fact_match.get("text", "")} if sid else None,
                    "The claim broadens an approved fact beyond its stated qualification or scope. Human verification is required.",
                    trace={"stage": "claims_ledger", "confidence": 0.95, "retrieved_source_ids": [sid] if sid else []},
                )
            )
            return findings, usage

    for claim in extract_claims(text):
        claim_text = claim["text"]
        fact_match = None
        if approved:
            claim_tokens = set(re.findall(r"[a-z0-9%]+", claim_text.casefold()))
            fact_match = next(
                (
                    fact for fact in approved
                    if fact.get("text")
                    and (
                        claim_tokens and claim_tokens.issubset(set(re.findall(r"[a-z0-9%]+", str(fact.get("text", "")).casefold())))
                        or bool(set(re.findall(r"[a-z0-9%]+", str(fact.get("text", "")).casefold())) & claim_tokens)
                    )
                ),
                None,
            )

        if fact_match:
            expired = _is_expired_fact(fact_match, now)
            broadened = _claim_extends_fact(claim_text, str(fact_match.get("text", "")))
            if expired or broadened:
                sid = str(fact_match["id"]) if fact_match.get("id") is not None else None
                explanation = (
                    "The claim broadens an approved fact beyond its stated qualification or scope."
                    if broadened else
                    "The closest approved fact has expired; human verification is required."
                )
                findings.append(
                    Finding(
                        str(uuid.uuid4()),
                        content_id,
                        version_no,
                        TextSpan(claim["start"], claim["end"]),
                        "claim",
                        "high",
                        "retrieval_ai",
                        "cannot_verify",
                        0.95 if expired or broadened else 0.65,
                        {"type": "fact", "id": sid, "clause_text": fact_match.get("text", "")} if sid else None,
                        explanation,
                        trace={
                            "stage": "claims_ledger",
                            "confidence": 0.95 if expired or broadened else 0.65,
                            "retrieved_source_ids": [sid] if sid else [],
                        },
                    )
                )
                continue

            usage.append({"fact_id": str(fact_match["id"]), "content_id": content_id, "version_no": version_no})
            continue

        findings.append(
            Finding(
                str(uuid.uuid4()),
                content_id,
                version_no,
                TextSpan(claim["start"], claim["end"]),
                "claim",
                "high",
                "retrieval_ai",
                "cannot_verify",
                0.65,
                None,
                "No approved fact was found that substantiates this claim. Human review is required.",
                trace={"stage": "claims_ledger", "confidence": 0.65, "retrieved_source_ids": []},
            )
        )

    return findings, usage
