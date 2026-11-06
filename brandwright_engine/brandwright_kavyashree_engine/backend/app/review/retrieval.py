"""Deterministic lexical retrieval fallback with pre-ranking safety filters."""
from __future__ import annotations

from datetime import datetime, timezone


def _expired(source: dict) -> bool:
    value = source.get("expires_at")
    if not value:
        return False
    try:
        expiry = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        # A malformed expiry must not be treated as an active approved fact.
        return True


def _confidential(source: dict) -> bool:
    return bool(source.get("confidential")) or str(source.get("sensitivity", "")).casefold() == "confidential"


class InMemoryRetriever:
    """Deterministic fallback; replace with a pgvector adapter when the KB is ready."""
    def __init__(self, sources):
        self.sources = sources

    def retrieve(self, text, intent="", channel=None, limit=8):
        query = f"{text} {intent}".casefold()
        scored = []
        for source in self.sources:
            # Filter before ranking so confidential/expired sources cannot occupy top-k slots.
            if source.get("status", "approved") != "approved":
                continue
            if _confidential(source) or _expired(source):
                continue
            channels = source.get("channels") or ["all"]
            if channel and "all" not in channels and channel not in channels:
                continue
            body = source.get("text", source.get("clause_text", ""))
            tokens = {x for x in body.casefold().split() if len(x) > 2}
            score = sum(token in query for token in tokens)
            if score:
                scored.append((score, source))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [source for _, source in scored[:limit]]
