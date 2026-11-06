# Integration notes for the shared Brandwright repository

## Kavyashree's module

The AI & Review Engine logic lives in `backend/app/review/`, `backend/app/trust/`, and the guideline drafting function in `backend/app/insights/`. The standalone HTTP adapter lives in `backend/app/review/api_service/`.

## Boundary with the main backend

The shared project build brief assigns the main backend scaffold, canonical schemas, authentication/RBAC, organisation scoping, queue, approval workflow and shared seed data to the backend/data owner. This package therefore keeps its API tables isolated with `review_engine_*` names and does not duplicate those responsibilities.

When merging:
1. Ask the backend owner for the canonical `Finding` schema and DB model names; map the adapter output to those types without changing the agreed Finding schema.
2. Mount the review router in the main FastAPI app behind its JWT and organisation-scope dependencies. The standalone service has no auth and must not be exposed publicly as-is.
3. Replace the standalone document/review persistence models with the canonical content/version/review/finding/fact-usage models. Do not keep duplicate content, organisation, user, rule or fact tables.
4. Replace synchronous review execution with the team's Redis/RQ job enqueue + status flow when the queue contract is available.
5. Feed approved, versioned rules/facts from the main knowledge-base API rather than trusting arbitrary client-supplied rule/fact payloads.
6. Connect the production pgvector retriever to the shared knowledge-base schema; the Claude adapter is present but must be configured and live-tested with the team's approved model and API key.
7. Merge the module's metadata-only AI-use records into the main app's canonical `ai_usage_log`, and send decision events to the shared append-only audit log.

## Current validation

- Core module and API tests: 40 passing.
- Alembic migration: tested successfully against a temporary SQLite database.
- API OpenAPI document: generated at `docs/openapi.json`.

## Not yet production-complete

- No JWT/RBAC or organisation isolation in this standalone adapter.
- No Redis/RQ background jobs; review endpoint currently runs synchronously.
- Claude API adapter is implemented with forced structured tool output, but live API calls have not been tested here; pgvector embedding/retrieval is not implemented yet.
- Standalone metadata-only AI-use logging is implemented; it still needs mapping to the shared canonical `ai_usage_log` and audit log.
- Brand-book parsing is a heuristic draft extractor; the guideline owner must approve each extracted rule.
- Image checks are deterministic but bounded: palette sampling, configured foreground/background contrast, alt-text presence, and logo minimum size when the caller supplies logo bounds. Automatic logo detection and vision-LLM checks are not implemented.
- No public deployment has been made.


## Step 6 completion in this package

The Trust Scorecard now reports micro precision/recall/F1, macro F1, per-category and per-sample metrics, and per-sample traces (matched labels, missed labels, unexpected findings, and pipeline retrieval metadata). Each API run is persisted in `review_engine_trust_runs`.

Guideline clarification drafts now retain decision evidence (decision ID, action, reason, and optional finding/content/quote/edit metadata) and return an explicit owner-approval warning. Drafts remain `draft`; no active guideline is changed. The evidence is persisted with each clarification.

The evaluation runner is deterministic given deterministic pipeline output. Real-world score quality still depends on the quality, size, and balance of the labelled `/eval` dataset.


## AI provider and privacy implementation

`BRANDWRIGHT_MODEL_MODE=mock` remains the default. To opt into Claude, set `BRANDWRIGHT_MODEL_MODE=claude`, `BRANDWRIGHT_ANTHROPIC_API_KEY`, and `BRANDWRIGHT_MODEL_NAME`, install `requirements-api.txt`, and send a review with `local_only=false`. The adapter uses forced structured tool output and drops findings whose source IDs were not retrieved. It does not call the model when no approved sources are retrieved. Live provider calls have not been verified in this build environment.

Before an external call, the privacy layer masks supported personal/confidential values while preserving character offsets, then rescans the exact outgoing payload and blocks it if supported sensitive patterns remain. Per-review AI usage metadata is persisted without storing content or redacted values. The standalone API still has no authentication or organisation isolation and must not be exposed publicly until mounted behind the host application's controls.

## Guideline Health endpoints

- `POST /api/engine/findings/{finding_id}/decision` stores accept/edit/dismiss decisions; dismiss requires a reason and edit requires edited text.
- `GET /api/engine/insights/guideline-health` computes per-rule dismissal and override rates, ranks likely unclear rules, and only raises the false-positive flag after the configured minimum number of decisions. These are triage signals, not automatic rule changes.
- `POST /api/engine/guidelines/clarifications` creates an evidence-linked draft; it never approves or edits the active guideline.
