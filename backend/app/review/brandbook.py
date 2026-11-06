"""Conservative brand-book text parser. Extracted rules are drafts for owner approval."""
import re

_CATEGORY_HINTS = {
    "terminology": ("term", "word", "phrase", "call", "refer to", "name"),
    "claims": ("claim", "proof", "evidence", "substantiat", "certif", "guarantee", "superlative"),
    "accessibility": ("contrast", "alt text", "accessible", "wcag", "screen reader"),
    "visual": ("logo", "colour", "color", "palette", "font", "visual"),
    "tone": ("tone", "voice", "friendly", "formal", "humour", "humor"),
}
_CHANNELS = ("website", "web", "social", "instagram", "linkedin", "email", "print", "packaging", "advert", "advertising")


def _category(text: str) -> str:
    lower = text.casefold()
    for category, hints in _CATEGORY_HINTS.items():
        if any(h in lower for h in hints):
            return category
    return "general"


def parse_brand_book(text: str) -> list[dict]:
    """Split guideline text into addressable rule drafts; never auto-approves them."""
    if not isinstance(text, str) or not text.strip():
        return []
    # Keep numbered clauses and bullet lines as separate candidates. Merge wrapped
    # continuation lines into the preceding candidate to avoid sentence fragments.
    chunks = re.split(r"(?m)(?=^\s*(?:\d+(?:\.\d+)*[.)]?\s+|[-*•]\s+))", text.strip())
    rules = []
    for chunk in chunks:
        lines = [re.sub(r"\s+", " ", line).strip() for line in chunk.splitlines() if line.strip()]
        clause = " ".join(lines).strip(" -*•")
        if len(clause) < 12:
            continue
        number = re.match(r"^(\d+(?:\.\d+)*)", clause)
        channels = [c for c in _CHANNELS if re.search(rf"\b{re.escape(c)}\b", clause, re.I)]
        rules.append({"id": f"extracted-{len(rules)+1:03d}",
                      "clause_number": number.group(1) if number else None,
                      "text": clause, "category": _category(clause),
                      "channel_tags": channels, "status": "draft",
                      "requires_owner_approval": True})
    return rules
