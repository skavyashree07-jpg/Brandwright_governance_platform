from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Callable, Protocol

EMBEDDING_DIMENSION = 1536


class Embedder(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]:
        ...


class DeterministicFakeEmbedder:
    """Local, repeatable feature-hash embedder for tests and offline development."""

    dimension = EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        tokens = re.findall(r"[\w%]+", text.casefold())
        features = tokens + [f"{left} {right}" for left, right in zip(tokens, tokens[1:])]
        vector = [0.0] * self.dimension
        for feature, count in Counter(features).items():
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimension
            sign = 1.0 if value & (1 << 63) else -1.0
            vector[index] += sign * count

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            vector[0] = 1.0
            return vector
        return [value / magnitude for value in vector]


_PROVIDERS: dict[str, Callable[[], Embedder]] = {
    "fake": DeterministicFakeEmbedder,
}


def register_embedder(name: str, factory: Callable[[], Embedder]) -> None:
    """Register a provider implementation without coupling retrieval to its vendor."""
    normalized = name.strip().casefold()
    if not normalized:
        raise ValueError("Embedder provider name cannot be empty")
    _PROVIDERS[normalized] = factory


def create_embedder(provider: str | None = None) -> Embedder:
    if provider is None:
        from app.config import settings

        provider = settings.EMBEDDING_PROVIDER
    normalized = provider.strip().casefold()
    try:
        embedder = _PROVIDERS[normalized]()
    except KeyError as exc:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown embedding provider '{provider}'. Registered providers: {supported}") from exc
    if embedder.dimension != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Embedding provider '{normalized}' returned dimension {embedder.dimension}; "
            f"the database schema requires {EMBEDDING_DIMENSION}"
        )
    return embedder


def term_embedding_text(preferred: str, banned: str, notes: str | None = None) -> str:
    parts = [f"Preferred term: {preferred}", f"Avoid: {banned}"]
    if notes and notes.strip():
        parts.append(f"Notes: {notes.strip()}")
    return ". ".join(parts)
