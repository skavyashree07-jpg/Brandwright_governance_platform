from .rule_engine import run_rule_engine
from .retrieval import InMemoryRetriever
from .llm_review import create_llm_client, build_ai_findings
from .claims import verify_claims
from .privacy import prepare_external_payload

def review_text(text, intent, rules, facts, content_id="demo-content", version_no=1,
                retriever=None, llm_client=None, local_only=False, confidential_strings=None,
                channel=None, progress_callback=None, raise_ai_errors=False):
    rule_findings = run_rule_engine(text, rules, content_id, version_no, channel=channel)
    if progress_callback:
        progress_callback("deterministic_checks", "completed", rule_findings)
    claim_findings, fact_usage = verify_claims(text, facts, content_id, version_no)
    if progress_callback:
        progress_callback("claim_verification", "completed", claim_findings)

    all_sources = rules + facts
    confidential_sources = [source for source in all_sources
                            if source.get("confidential") or str(source.get("sensitivity", "")).casefold() == "confidential"]
    sensitive_values = list(confidential_strings or [])
    for source in confidential_sources:
        for field in ("text", "clause_text", "match_text"):
            value = source.get(field)
            if isinstance(value, str) and value.strip():
                sensitive_values.append(value)
        sensitive_values.extend(source.get("confidential_strings", []) or [])

    retrieved = (retriever or InMemoryRetriever(all_sources)).retrieve(text, intent, channel=channel)
    content_payload = prepare_external_payload(text, sensitive_values, local_only)
    intent_payload = prepare_external_payload(intent, sensitive_values, local_only)
    redacted_sources, source_redactions, source_blocked = [], [], False
    if not local_only:
        for source in retrieved:
            safe_source = dict(source)
            for field in ("text", "clause_text", "match_text", "explanation", "suggestion"):
                value = safe_source.get(field)
                if isinstance(value, str):
                    safe = prepare_external_payload(value, sensitive_values, False)
                    if not safe["allowed"]:
                        source_blocked = True
                        break
                    safe_source[field] = safe["text"]
                    source_redactions.extend(safe["redactions"])
            if source_blocked:
                break
            redacted_sources.append(safe_source)

    privacy_allowed = (content_payload["allowed"] and intent_payload["allowed"]
                       and not source_blocked and (local_only or len(redacted_sources) == len(retrieved)))
    payload_redactions = content_payload["redactions"] + intent_payload["redactions"] + source_redactions
    privacy_reason = (content_payload.get("reason") or intent_payload.get("reason")
                      or ("Egress privacy check failed for a retrieved source." if source_blocked else None))
    ai_findings, services, ai_usage = [], [], []
    if progress_callback:
        progress_callback("ai_review", "running", [])
    if privacy_allowed and not local_only and retrieved:
        client = None
        service_name = "configured-llm"
        try:
            client = llm_client or create_llm_client()
            service_name = getattr(client, "service_name", service_name)
            ai_findings = build_ai_findings(content_payload["text"], intent_payload["text"],
                redacted_sources, client, content_id, version_no, source_lookup=retrieved)
            services.append(service_name)
            call_error = None
        except Exception as exc:
            # A provider/configuration failure must not discard deterministic findings.
            # Persist only the exception class, never request or response contents.
            call_error = type(exc).__name__
            if progress_callback:
                progress_callback("ai_review", "failed", [])
            if raise_ai_errors:
                raise
        else:
            if progress_callback:
                progress_callback("ai_review", "completed", ai_findings)
        redaction_counts = {}
        for record in payload_redactions:
            redaction_counts[record["type"]] = redaction_counts.get(record["type"], 0) + record["count"]
        ai_usage.append({
            "service": service_name, "purpose": "content_review",
            "model": getattr(client, "model", None) if client else None,
            "external": service_name not in {"mock-llm", "configured-llm"},
            "redacted": bool(payload_redactions), "redaction_counts": redaction_counts,
            "input_chars": len(content_payload["text"]) + len(intent_payload["text"]),
            "output_chars": len(str(ai_findings)), "error": call_error,
            "blocked": bool(call_error),
        })
    elif not local_only and not privacy_allowed:
        redaction_counts = {}
        for record in payload_redactions:
            redaction_counts[record["type"]] = redaction_counts.get(record["type"], 0) + record["count"]
        ai_usage.append({
            "service": "external-llm", "purpose": "content_review", "model": None,
            "external": False, "redacted": bool(payload_redactions),
            "redaction_counts": redaction_counts, "input_chars": 0, "output_chars": 0,
            "error": privacy_reason or "Privacy check blocked request", "blocked": True,
        })
        if progress_callback:
            progress_callback("ai_review", "completed", [])
    else:
        if progress_callback:
            progress_callback("ai_review", "completed", [])
    ai_skipped_reason = None
    if not local_only and privacy_allowed and not retrieved:
        ai_skipped_reason = "No approved sources were retrieved."
    elif not privacy_allowed:
        ai_skipped_reason = privacy_reason or "Privacy check blocked request."

    return {"findings": rule_findings + claim_findings + ai_findings,
        "fact_usage": fact_usage, "retrieved_source_ids": [str(s["id"]) for s in retrieved if s.get("id")],
        "ai_services_used": services, "ai_usage": ai_usage,
        "redactions": payload_redactions, "local_only": local_only,
        "ai_skipped_reason": ai_skipped_reason,
        "privacy": {"external_calls": sum(1 for x in ai_usage if x.get("external")),
                    "blocked_calls": sum(1 for x in ai_usage if x.get("blocked")),
                    "redacted_calls": sum(1 for x in ai_usage if x.get("redacted")),
                    "unredacted_external_calls": sum(1 for x in ai_usage if x.get("external") and not x.get("redacted"))}}
