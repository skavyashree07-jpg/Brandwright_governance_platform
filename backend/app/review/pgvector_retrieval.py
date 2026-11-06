from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Fact, Rule, Term
from app.review.embeddings import Embedder, create_embedder, term_embedding_text


class PgVectorRetriever:
    """Organisation-scoped cosine-similarity search over approved KB sources."""

    def __init__(
        self,
        db: Session,
        organisation_id: UUID,
        embedder: Embedder | None = None,
    ):
        self.db = db
        self.organisation_id = organisation_id
        self.embedder = embedder or create_embedder()

    def _query_rows(self, model: Any, query_vector: list[float], limit: int, channel: str | None):
        distance = model.embedding.cosine_distance(query_vector).label("distance")
        query = self.db.query(model, distance).filter(
            model.organisation_id == self.organisation_id,
            model.embedding.is_not(None),
        )
        if model is Rule:
            query = query.filter(
                Rule.status == "approved",
                or_(Rule.sensitivity.is_(None), func.lower(Rule.sensitivity) != "confidential"),
            )
            if channel:
                query = query.filter(
                    or_(
                        Rule.channels.is_(None),
                        Rule.channels == [],
                        Rule.channels.contains(["all"]),
                        Rule.channels.contains([channel]),
                        Rule.channels.contains([channel.casefold()]),
                    )
                )
        elif model is Fact:
            query = query.filter(
                Fact.status == "approved",
                or_(Fact.expires_at.is_(None), Fact.expires_at > datetime.utcnow()),
            )
        return query.order_by(distance).limit(limit).all()

    @staticmethod
    def _source(model: Any, row: Any, similarity: float) -> dict[str, Any]:
        if model is Rule:
            return {
                "id": str(row.id),
                "source_type": "rule",
                "text": row.text,
                "category": row.category,
                "channels": row.channels or ["all"],
                "status": row.status,
                "sensitivity": row.sensitivity,
                "type": row.type,
                "config": row.config or {},
                "similarity_score": similarity,
            }
        if model is Fact:
            return {
                "id": str(row.id),
                "source_type": "fact",
                "text": row.text,
                "status": row.status,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "sensitivity": "normal",
                "similarity_score": similarity,
            }
        return {
            "id": str(row.id),
            "source_type": "rule",
            "text": row.notes or f"Use “{row.preferred}” instead of “{row.banned}”.",
            "category": "terminology",
            "channels": ["all"],
            "status": "approved",
            "type": "banned_term",
            "config": {"term": row.banned, "replacement": row.preferred},
            "similarity_score": similarity,
        }

    def retrieve(self, text: str, intent: str = "", channel: str | None = None, limit: int = 8):
        if limit <= 0:
            return []
        query_vector = self.embedder.embed(f"{text} {intent}".strip())
        ranked: list[tuple[float, str, dict[str, Any]]] = []
        for model in (Rule, Fact, Term):
            for row, distance in self._query_rows(model, query_vector, limit, channel):
                similarity = 1.0 - float(distance)
                source = self._source(model, row, similarity)
                ranked.append((similarity, str(row.id), source))
        ranked.sort(key=lambda result: (-result[0], result[1]))
        return [source for _, _, source in ranked[:limit]]


def embedding_text_for(model: Any, row: Any) -> str:
    if model is Rule:
        return row.text
    if model is Fact:
        return row.text
    return term_embedding_text(row.preferred, row.banned, row.notes)


def backfill_embeddings(db: Session, embedder: Embedder | None = None, batch_size: int = 100) -> dict[str, int]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    embedder = embedder or create_embedder()
    counts: dict[str, int] = {}
    for model in (Rule, Fact, Term):
        count = 0
        while True:
            rows = (
                db.query(model)
                .filter(model.embedding.is_(None))
                .order_by(model.id)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break
            for row in rows:
                row.embedding = embedder.embed(embedding_text_for(model, row))
            db.commit()
            count += len(rows)
        counts[model.__tablename__] = count
    return counts
