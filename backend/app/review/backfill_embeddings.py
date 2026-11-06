from __future__ import annotations

import argparse
import json

from app.db import SessionLocal
from app.review.pgvector_retrieval import backfill_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate embeddings for existing brand knowledge records.")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    with SessionLocal() as db:
        counts = backfill_embeddings(db, batch_size=args.batch_size)
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
