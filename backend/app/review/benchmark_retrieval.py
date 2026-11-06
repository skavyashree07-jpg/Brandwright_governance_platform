from __future__ import annotations

import argparse
import json
import statistics
import time
from uuid import UUID

from app.db import SessionLocal
from app.review.integration import _fact_sources, _rule_sources
from app.review.pgvector_retrieval import PgVectorRetriever
from app.review.retrieval import InMemoryRetriever


def _measure(retriever, text: str, intent: str, channel: str | None, limit: int, repeat: int):
    durations = []
    for _ in range(repeat):
        started = time.perf_counter()
        retriever.retrieve(text, intent, channel=channel, limit=limit)
        durations.append((time.perf_counter() - started) * 1000)
    return {
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(sorted(durations)[min(len(durations) - 1, int(len(durations) * 0.95))], 3),
        "runs": repeat,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare memory and pgvector retrieval latency.")
    parser.add_argument("--organisation-id", required=True, type=UUID)
    parser.add_argument("--text", required=True)
    parser.add_argument("--intent", default="")
    parser.add_argument("--channel")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--repeat", type=int, default=30)
    args = parser.parse_args()
    if args.top_k < 1 or args.repeat < 1:
        parser.error("--top-k and --repeat must be positive")

    with SessionLocal() as db:
        sources = _rule_sources(db, args.organisation_id) + _fact_sources(db, args.organisation_id)
        memory = InMemoryRetriever(sources)
        pgvector = PgVectorRetriever(db, args.organisation_id)
        results = {
            "memory": _measure(memory, args.text, args.intent, args.channel, args.top_k, args.repeat),
            "pgvector": _measure(pgvector, args.text, args.intent, args.channel, args.top_k, args.repeat),
            "organisation_id": str(args.organisation_id),
            "top_k": args.top_k,
            "source_count": len(sources),
            "note": "The fake embedder is used unless EMBEDDING_PROVIDER selects another registered provider.",
        }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
