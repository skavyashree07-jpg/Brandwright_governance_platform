"""Run the bundled fictional labelled set locally (smoke test, not a benchmark)."""
import json
from pathlib import Path
from app.review.pipeline import review_text
from app.trust.evaluator import evaluate_dataset

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = json.loads((ROOT / "eval" / "demo_samples.json").read_text(encoding="utf-8"))


def pipeline(sample):
    result = review_text(
        sample["content"], sample.get("intent", "Brand compliance review"),
        sample.get("rules", []), sample.get("facts", []),
        content_id=sample["id"], local_only=True,
    )
    return {
        "findings": [finding.to_dict() for finding in result["findings"]],
        "trace": {
            "retrieved_source_ids": result.get("retrieved_source_ids", []),
            "local_only": True,
            "ai_services_used": result.get("ai_services_used", []),
        },
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_dataset(SAMPLES, pipeline), indent=2))
