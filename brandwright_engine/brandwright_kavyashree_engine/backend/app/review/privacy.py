"""Fail-closed privacy redaction for external model requests.

Redaction preserves character offsets by masking each sensitive span with the
same number of ``X`` characters. Logs contain counts/types only, never values.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS = [
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("aadhaar", re.compile(r"(?<!\d)(?:\d{4}[ -]?){2}\d{4}(?!\d)")),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I)),
    ("ip_address", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("api_key", re.compile(r"\b(?:sk|pk|api|key)[_-][A-Za-z0-9_-]{12,}\b", re.I)),
    ("phone", re.compile(r"(?<!\d)(?:\+91[ -]?)?[6-9]\d{9}(?!\d)")),
    ("card_candidate", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")),
]
NAME_PATTERNS = [
    re.compile(r"\b(?:Dr|Mr|Mrs|Ms|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"),
    re.compile(r"\bmy name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", re.I),
    re.compile(r"(?im)^(?:regards|sincerely|best regards|thanks)[, ]*\n\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*$"),
]


@dataclass
class RedactionResult:
    text: str
    redactions: list[dict]


def _luhn_valid(value: str) -> bool:
    digits = [int(x) for x in re.sub(r"\D", "", value)]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> tuple[str, int]:
    if not spans:
        return text, 0
    chars = list(text)
    count = 0
    occupied: set[int] = set()
    for start, end in sorted(spans):
        if start < 0 or end <= start or any(i in occupied for i in range(start, end)):
            continue
        for i in range(start, end):
            chars[i] = "X"
            occupied.add(i)
        count += 1
    return "".join(chars), count


def redact_sensitive(text: str, confidential_strings=None) -> RedactionResult:
    output = text
    records = []
    for value in sorted({str(x) for x in (confidential_strings or []) if x}, key=len, reverse=True):
        spans = [(m.start(), m.end()) for m in re.finditer(re.escape(value), output, re.I)]
        output, count = _mask_spans(output, spans)
        if count:
            records.append({"type": "confidential", "count": count})

    for label, pattern in PATTERNS:
        matches = list(pattern.finditer(output))
        if label == "card_candidate":
            matches = [m for m in matches if _luhn_valid(m.group())]
            label = "payment_card"
        spans = [(m.start(), m.end()) for m in matches]
        output, count = _mask_spans(output, spans)
        if count:
            records.append({"type": label, "count": count})

    name_spans = []
    for pattern in NAME_PATTERNS:
        for match in pattern.finditer(output):
            # For "my name is" and sign-offs, mask the captured name only.
            name_spans.append(match.span(1) if match.lastindex else match.span())
    output, name_count = _mask_spans(output, name_spans)
    if name_count:
        records.append({"type": "person_name", "count": name_count})
    return RedactionResult(output, records)


def _contains_sensitive(text: str) -> bool:
    for label, pattern in PATTERNS:
        matches = list(pattern.finditer(text))
        if label == "card_candidate":
            matches = [m for m in matches if _luhn_valid(m.group())]
        if matches:
            return True
    for pattern in NAME_PATTERNS:
        if pattern.search(text):
            return True
    return False


def prepare_external_payload(text, confidential_strings=None, local_only=False):
    if local_only:
        return {"allowed": False, "text": None, "redactions": [], "reason": "Local-only mode is enabled."}
    result = redact_sensitive(text, confidential_strings)
    # Re-scan the exact payload after redaction. If any supported sensitive
    # pattern remains, fail closed and do not send the content to the provider.
    if _contains_sensitive(result.text):
        return {"allowed": False, "text": None, "redactions": result.redactions,
                "reason": "Egress privacy check failed; external call blocked."}
    return {"allowed": True, "text": result.text, "redactions": result.redactions, "reason": None}
