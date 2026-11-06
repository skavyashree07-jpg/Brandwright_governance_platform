# AI & Review Engine API contract

Base path: `/api/engine`  
Local API docs: `/docs`  
This is a **module-level adapter contract**, not a replacement for Brandwright's main API contract. The main backend owner supplies authentication, organisation scoping, the canonical Finding schema, queue and shared database models. Mount these routes behind those existing controls during integration.

## Health
- `GET /health` — service health.

## Documents
- `POST /api/engine/documents` — multipart field `file`; supports TXT, MD, CSV, DOCX, PDF, PNG, JPG/JPEG, TIFF, BMP and WEBP. Returns extracted text, character spans, page metadata and warnings. Original file bytes are not retained by this adapter.
- `POST /api/engine/documents/{document_id}/review` — runs the review pipeline on an uploaded document.

## Reviews
- `POST /api/engine/reviews` — runs a synchronous review of supplied text.
- `GET /api/engine/reviews?limit=25` — recent review summaries.
- `GET /api/engine/reviews/{review_id}` — complete result and findings.
- `GET /api/engine/reviews/{review_id}/fact-usage` — facts used by that review.
- `GET /api/engine/reviews/{review_id}/ai-usage` — metadata-only provider, model, redaction and blocked-call log; content is never stored in this log.

Example request:

```json
{
  "content": "Our battery is the safest on the market.",
  "intent": "Announce the battery product to business customers",
  "content_id": "campaign-001",
  "version_no": 1,
  "rules": [
    {"id": "rule-4.2", "text": "Avoid unsupported superlatives", "type": "superlative", "config": {"terms": ["safest"]}}
  ],
  "facts": [],
  "local_only": true,
  "confidential_strings": []
}
```

Finding response preserves the current engine Finding fields: `id`, `content_id`, `version_no`, `span` (`start`, `end`, `page`), `category`, `severity`, `check_type`, `status`, `confidence`, `source`, `explanation`, `suggestion`, `decision`, and `trace`.

## Trust scorecard
- `POST /api/engine/trust/run` — evaluates 1–500 labelled samples and stores a run. Send `{"samples": [...]}` for a team dataset or omit the body to use the bundled fictional smoke-test dataset.
- `GET /api/engine/trust/scorecard` — latest result and up to 50 historical runs.

## Guideline and image checks
- `POST /api/engine/guidelines/parse` — splits supplied brand-book text into numbered rule drafts with category/channel hints. All extracted rules require owner approval.
- `POST /api/engine/images/review` — multipart image plus optional `alt_text`, `allowed_palette` (comma-separated hex colours), `logo_bbox` (x,y,width,height), minimum logo dimensions, and foreground/background colours for WCAG contrast calculation. Logo presence/size is only checked when a bounding box is supplied by the caller; the module does not autonomously locate a logo.

## Guideline Health and clarification drafting
- `POST /api/engine/findings/{finding_id}/decision` — records accept/edit/dismiss; dismissal requires a reason and edit requires edited text.
- `GET /api/engine/insights/guideline-health` — per-rule decision counts, dismissal rate, override rate, clarity-risk ranking, and sample-size-aware false-positive flag.
- `POST /api/engine/guidelines/clarifications` — drafts and stores an evidence-linked clarification.
- `GET /api/engine/guidelines/clarifications` — lists drafts and their motivating decision evidence.

Drafts remain `draft` and explicitly require guideline-owner approval. Approval is not performed by this module.

## Data and security boundaries

The standalone development database uses separate `review_engine_*` tables. For the shared app, map these records to the canonical models supplied by the backend owner rather than creating duplicate content, user, organisation, rule or fact tables. Apply the host app's JWT/RBAC and organisation filter to every route. The standalone app is for local development only until those controls are mounted.

The default local-only setting prevents external LLM calls in the pipeline. The bundled provider can run in deterministic mock mode or use the optional Anthropic Claude SDK adapter (`BRANDWRIGHT_MODEL_MODE=claude`, API key and model configured). Claude mode has not been live-tested in this environment. The retriever remains an in-memory lexical adapter; pgvector-backed semantic retrieval is still an integration task. External calls are redacted and fail closed on a second egress scan; metadata-only AI-use records are persisted. OCR for scanned PDFs/images requires the Tesseract executable installed on the host. The image review endpoint supports deterministic palette sampling, configured contrast, alt-text presence, and logo bounds when supplied; it does not autonomously detect logos.

The bundled `eval/demo_samples.json` contains five fictional samples for a smoke test only. The project brief asks for 30–40 human-labelled samples; do not report the demo metrics as production accuracy.
