from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Fact, Organisation, Rule, Term
from app.review.embeddings import DeterministicFakeEmbedder
from app.review.llm_review import MockLLMClient
from app.review.pipeline import review_text
from app.review.pgvector_retrieval import PgVectorRetriever, backfill_embeddings


class FixedEmbedder:
    dimension = 1536

    def embed(self, text: str) -> list[float]:
        return [1.0] + [0.0] * (self.dimension - 1)


class BackfillSession:
    def __init__(self, rows_by_model):
        self.rows_by_model = rows_by_model

    def query(self, model):
        return BackfillQuery(self.rows_by_model[model])

    def commit(self):
        pass


class BackfillQuery:
    def __init__(self, rows):
        self.rows = rows
        self.batch_size = None

    def filter(self, *_conditions):
        return self

    def order_by(self, *_columns):
        return self

    def limit(self, size):
        self.batch_size = size
        return self

    def all(self):
        return [row for row in self.rows if row.embedding is None][: self.batch_size]


def _vector(x: float, y: float) -> list[float]:
    return [x, y] + [0.0] * 1534


@pytest.fixture(scope="module")
def pg_session_factory():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL/pgvector integration tests.")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def _new_org(db, name: str):
    org = Organisation(name=f"{name}-{uuid4()}")
    db.add(org)
    db.flush()
    return org


def _rule(org_id, text_value: str, embedding: list[float], status: str = "approved"):
    return Rule(
        organisation_id=org_id,
        clause_number=str(uuid4()),
        text=text_value,
        category="messaging",
        channels=["all"],
        status=status,
        sensitivity="normal",
        embedding=embedding,
    )


def test_deterministic_fake_embedder_is_stable_and_normalized():
    embedder = DeterministicFakeEmbedder()
    first = embedder.embed("Brand voice must stay clear.")
    second = embedder.embed("Brand voice must stay clear.")

    assert first == second
    assert len(first) == 1536
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_backfill_is_idempotent_without_database():
    rules = [SimpleNamespace(id=uuid4(), text="A guideline", embedding=None)]
    facts = [SimpleNamespace(id=uuid4(), text="A verified fact", embedding=None)]
    terms = [SimpleNamespace(
        id=uuid4(), preferred="preferred phrase", banned="banned phrase",
        notes="Use the preferred phrase.", embedding=None,
    )]
    db = BackfillSession({Rule: rules, Fact: facts, Term: terms})

    first = backfill_embeddings(db, FixedEmbedder(), batch_size=1)
    saved = [row.embedding[:] for row in rules + facts + terms]
    second = backfill_embeddings(db, FixedEmbedder(), batch_size=1)

    assert first == {"rules": 1, "facts": 1, "terms": 1}
    assert second == {"rules": 0, "facts": 0, "terms": 0}
    assert [row.embedding for row in rules + facts + terms] == saved


def test_pgvector_retrieval_is_organisation_scoped(pg_session_factory):
    db = pg_session_factory()
    org_a = _new_org(db, "retrieval-a")
    org_b = _new_org(db, "retrieval-b")
    rule_a = _rule(org_a.id, "Rule in organisation A", _vector(1, 0))
    rule_b = _rule(org_b.id, "Rule in organisation B", _vector(1, 0))
    db.add_all([rule_a, rule_b])
    db.commit()
    expected_id = str(rule_a.id)

    try:
        retrieved = PgVectorRetriever(db, org_a.id, FixedEmbedder()).retrieve("query", limit=8)
        assert [source["id"] for source in retrieved] == [expected_id]
        assert retrieved[0]["similarity_score"] == pytest.approx(1.0)
    finally:
        db.delete(rule_a)
        db.delete(rule_b)
        db.delete(org_a)
        db.delete(org_b)
        db.commit()
        db.close()


def test_pgvector_retrieval_returns_global_top_k_in_similarity_order(pg_session_factory):
    db = pg_session_factory()
    org = _new_org(db, "retrieval-order")
    best = _rule(org.id, "Best match", _vector(1, 0))
    second = _rule(org.id, "Second match", _vector(0.8, 0.6))
    third = _rule(org.id, "Third match", _vector(0, 1))
    unapproved = _rule(org.id, "Pending match", _vector(1, 0), status="pending")
    db.add_all([best, second, third, unapproved])
    db.commit()

    try:
        retrieved = PgVectorRetriever(db, org.id, FixedEmbedder()).retrieve("query", limit=2)
        assert [source["id"] for source in retrieved] == [str(best.id), str(second.id)]
        assert retrieved[0]["similarity_score"] > retrieved[1]["similarity_score"]
        assert all(source["id"] != str(unapproved.id) for source in retrieved)
    finally:
        for rule in (best, second, third, unapproved):
            db.delete(rule)
        db.delete(org)
        db.commit()
        db.close()


def test_pipeline_keeps_finding_contract_with_retriever():
    source_id = str(uuid4())
    source = {
        "id": source_id,
        "source_type": "rule",
        "text": "Avoid using overexcited language.",
        "category": "messaging",
        "channels": ["all"],
        "status": "approved",
        "match_text": "super exciting",
        "suggestion": "Promote the product with confident language.",
    }

    class Retriever:
        def retrieve(self, text, intent="", channel=None, limit=8):
            return [source]

    result = review_text(
        "Our product is super exciting.",
        "Promote the product",
        [source],
        [],
        content_id="content-contract",
        version_no=4,
        retriever=Retriever(),
        llm_client=MockLLMClient(),
    )
    finding = next(item.to_dict() for item in result["findings"] if item.check_type == "retrieval_ai")

    assert set(finding) == {
        "id", "content_id", "version_no", "span", "category", "severity",
        "check_type", "status", "confidence", "source", "explanation",
        "suggestion", "decision", "trace",
    }
    assert finding["content_id"] == "content-contract"
    assert finding["version_no"] == 4
    assert finding["source"]["id"] == source_id
    assert finding["status"] == "violation"
    assert finding["suggestion"]["intent_preserved"] is True
