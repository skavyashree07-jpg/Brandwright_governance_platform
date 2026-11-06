"""Deterministic Trust Scorecard evaluation for labelled review samples.

Expected issue labels may be strings (usually category names) or objects. Object
labels can identify a specific rule/finding with ``rule_id``, ``source_id`` or
``id``; otherwise matching falls back to category + issue text. This keeps the
scorecard useful while labelled data evolves.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Iterable


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _category(item: Any) -> str:
    if isinstance(item, str):
        return _normalise(item)
    if not isinstance(item, dict):
        return _normalise(item)
    return _normalise(item.get("category") or item.get("issue_type") or item.get("type") or "unknown")


def _key(item: Any) -> tuple[str, ...]:
    """Stable matching key; category-only labels remain backward compatible."""
    if isinstance(item, str):
        return ("category", _normalise(item))
    if not isinstance(item, dict):
        return ("value", _normalise(item))
    category = _category(item)
    source = item.get("rule_id") or item.get("source_id")
    source_obj = item.get("source")
    if not source and isinstance(source_obj, dict):
        source = source_obj.get("id") or source_obj.get("rule_id")
    if source:
        return ("source", _normalise(source), category)
    issue = item.get("issue") or item.get("description") or item.get("explanation") or item.get("text")
    if issue:
        return ("issue", category, _normalise(issue))
    # Category-only object is intentionally equivalent to a category string.
    return ("category", category)


def _is_category_only(item: Any) -> bool:
    if isinstance(item, str):
        return True
    if not isinstance(item, dict):
        return True
    has_source = bool(item.get("rule_id") or item.get("source_id"))
    source_obj = item.get("source")
    has_source = has_source or (isinstance(source_obj, dict) and bool(source_obj.get("id") or source_obj.get("rule_id")))
    has_issue = bool(item.get("issue") or item.get("description") or item.get("explanation") or item.get("text"))
    return not has_source and not has_issue


def _compare(expected: list[Any], predicted: list[Any]) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Match exact identifiers first, then allow category-only labels to match by category."""
    unmatched_e, unmatched_p = set(range(len(expected))), set(range(len(predicted)))
    pairs: list[tuple[int, int]] = []
    p_by_key: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for j, item in enumerate(predicted):
        p_by_key[_key(item)].append(j)
    for i, item in enumerate(expected):
        candidates = p_by_key.get(_key(item), [])
        j = next((candidate for candidate in candidates if candidate in unmatched_p), None)
        if j is not None:
            pairs.append((i, j)); unmatched_e.remove(i); unmatched_p.remove(j)
    # A category-only expected label means "at least one finding in this category".
    for i in list(unmatched_e):
        if not _is_category_only(expected[i]):
            continue
        j = next((candidate for candidate in unmatched_p
                  if _category(predicted[candidate]) == _category(expected[i])), None)
        if j is not None:
            pairs.append((i, j)); unmatched_e.remove(i); unmatched_p.remove(j)
    # Symmetric fallback for category-only predicted labels.
    for j in list(unmatched_p):
        if not _is_category_only(predicted[j]):
            continue
        i = next((candidate for candidate in unmatched_e
                  if _category(expected[candidate]) == _category(predicted[j])), None)
        if i is not None:
            pairs.append((i, j)); unmatched_e.remove(i); unmatched_p.remove(j)
    return pairs, sorted(unmatched_e), sorted(unmatched_p)


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else (1.0 if not fn else 0.0),
        "recall": round(tp / (tp + fn), 4) if tp + fn else 1.0,
        "f1": round((2 * tp) / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) else 1.0,
    }


def calculate_metrics(expected: Iterable[Any], predicted: Iterable[Any]) -> dict[str, Any]:
    pairs, missed, unexpected = _compare(list(expected), list(predicted))
    return _prf(len(pairs), len(unexpected), len(missed))


def evaluate_dataset(samples: list[dict[str, Any]], pipeline: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    """Run a labelled dataset and return aggregate, category, sample and trace metrics."""
    totals = {"true_positive": 0, "false_positive": 0, "false_negative": 0}
    category_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    traces: list[dict[str, Any]] = []
    sample_metrics: list[dict[str, Any]] = []

    for sample in samples:
        raw_result = pipeline(sample)
        findings = raw_result.get("findings", []) if isinstance(raw_result, dict) else raw_result
        predicted = [f.to_dict() if hasattr(f, "to_dict") else f for f in (findings or [])]
        expected = sample.get("expected_issues", []) or []
        pairs, missed_indices, unexpected_indices = _compare(list(expected), list(predicted))
        metrics = _prf(len(pairs), len(unexpected_indices), len(missed_indices))
        for key in totals:
            totals[key] += metrics[key]

        matched_by_category: dict[str, int] = defaultdict(int)
        expected_by_category: dict[str, int] = defaultdict(int)
        predicted_by_category: dict[str, int] = defaultdict(int)
        for i, _ in pairs:
            matched_by_category[_category(expected[i])] += 1
        for item in expected:
            expected_by_category[_category(item)] += 1
        for item in predicted:
            predicted_by_category[_category(item)] += 1
        for category in set(expected_by_category) | set(predicted_by_category):
            category_counts[category]["tp"] += matched_by_category[category]
            category_counts[category]["fp"] += max(0, predicted_by_category[category] - matched_by_category[category])
            category_counts[category]["fn"] += max(0, expected_by_category[category] - matched_by_category[category])

        traces.append({
            "sample_id": sample.get("id"),
            "matched_expected": [expected[i] for i, _ in pairs],
            "missed_expected": [expected[i] for i in missed_indices],
            "unexpected_findings": [predicted[j] for j in unexpected_indices],
            "findings": predicted,
            "pipeline_trace": raw_result.get("trace", {}) if isinstance(raw_result, dict) else {},
        })
        sample_metrics.append({"sample_id": sample.get("id"), **metrics})

    aggregate = _prf(totals["true_positive"], totals["false_positive"], totals["false_negative"])
    per_category = {name: _prf(v["tp"], v["fp"], v["fn"]) for name, v in sorted(category_counts.items())}
    macro_f1 = round(sum(v["f1"] for v in per_category.values()) / len(per_category), 4) if per_category else 1.0
    return {
        **aggregate,
        "macro_f1": macro_f1,
        "sample_count": len(samples),
        "per_category": per_category,
        "sample_metrics": sample_metrics,
        "traces": traces,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


class TrustScorecard:
    """In-memory helper; the API persists each run in EngineTrustRun."""
    def __init__(self):
        self.history: list[dict[str, Any]] = []

    def run(self, samples: list[dict[str, Any]], pipeline: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
        result = evaluate_dataset(samples, pipeline)
        result["run_no"] = len(self.history) + 1
        self.history.append(result)
        return result

    def get(self) -> dict[str, Any]:
        return {"latest": self.history[-1] if self.history else None, "history": self.history}
