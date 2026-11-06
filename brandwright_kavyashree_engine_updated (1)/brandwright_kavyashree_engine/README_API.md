# Run Kavyashree's AI & Review Engine API

This adds a runnable FastAPI + SQLAlchemy service around the existing AI & Review Engine. It is intentionally isolated under `backend/app/review/api_service/` and uses `review_engine_*` development tables so it does not overwrite the shared Brandwright schema.

## 1. Install

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# If PowerShell blocks activation, use: .venv\Scripts\python.exe -m pip install -r requirements-api.txt

pip install -r requirements-api.txt
```

For image OCR, install the Tesseract OCR executable separately and add it to PATH. Text, DOCX and selectable-text PDF review do not require Tesseract.

## 2. Configure and run

Copy `.env.example` to `.env` if you want to change settings. SQLite is the default for local use.

From the project root:

```bash
# Windows PowerShell
$env:PYTHONPATH = "backend"
python -m uvicorn app.review.api_service.main:app --reload --app-dir backend
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation and `http://127.0.0.1:8000/health` for health status.

## 3. API capabilities

The module exposes document ingestion, text review, review history, fact usage, per-review AI-use logs, trust-scorecard runs/history, brand-book rule extraction drafts, deterministic image checks (palette sampling, configured contrast, alt-text presence, and logo size when a caller supplies logo bounds), human finding decisions, Guideline Health analytics, and evidence-linked clarification drafts. OpenAPI is available at `/docs`.

### Step 6: Trust Scorecard and Guideline Health

- `POST /api/engine/trust/run` evaluates labelled samples and persists each run. Send `{"samples": [...]}` for your team's labelled set, or omit the body to run the bundled fictional smoke-test dataset in `eval/demo_samples.json`.
- Metrics include micro precision/recall/F1, macro F1, TP/FP/FN counts, per-category metrics, per-sample metrics, and traces showing matched, missed, and unexpected findings plus retrieved source IDs.
- Labels can be category strings (for example `"tone"`) or objects keyed by `rule_id` / `source_id`; object labels can also use category plus issue text.
- `GET /api/engine/trust/scorecard` returns the latest run and recent history.
- `POST /api/engine/guidelines/clarifications` creates a draft grounded in supplied reviewer decisions. It records decision IDs and the evidence fields supplied with those decisions. It never changes an active rule; owner approval remains mandatory.
- `GET /api/engine/guidelines/clarifications` lists saved drafts and their evidence.
- `POST /api/engine/findings/{finding_id}/decision` records an accept/edit/dismiss decision. Dismissals require a reason; edits require edited text.
- `GET /api/engine/insights/guideline-health` reports per-rule accept/edit/dismiss counts, dismissal and override rates, clarity-risk ranking, and a cautious false-positive flag after the minimum sample count.
- `GET /api/engine/reviews/{review_id}/ai-usage` returns provider/model, redaction counts, sizes and blocked/error metadata. It never returns content or redacted values.

The bundled set has five fictional samples and is only a smoke test. The team brief calls for 30–40 human-labelled pieces in `/eval`; replace/extend the demo set with reviewed labels before reporting meaningful accuracy. Run it locally with `PYTHONPATH=backend python scripts/run_demo_scorecard.py`.

## 4. Run tests

```bash
$env:PYTHONPATH = "backend"
python -m pytest -q tests/kavyashree tests/kavyashree_api
```

## 5. PostgreSQL

Set `BRANDWRIGHT_DATABASE_URL` to a PostgreSQL SQLAlchemy URL, for example:

```text
postgresql+psycopg://USER:PASSWORD@localhost:5432/brandwright
```

For migration-managed deployments, from `backend/` run `alembic upgrade head`. The migration creates only this module's prefixed tables. In a shared Brandwright deployment, have the main backend owner merge the models into the canonical migration instead of running a parallel migration blindly.

## 6. Important integration boundaries

- This service does not implement login, JWT, RBAC, organisation scoping, the review queue, or the approval state machine. Those belong to the main backend owner. Do not expose this standalone API publicly without mounting the host application's auth and organisation-scope dependencies.
- It accepts rule/fact payloads in review requests for standalone use. In the shared app, replace these inputs with the approved, versioned knowledge-base records supplied by the main backend.
- The LLM provider is selectable: `BRANDWRIGHT_MODEL_MODE=mock` is the safe offline default; `claude` enables the Anthropic SDK adapter with forced structured tool output. Set `BRANDWRIGHT_ANTHROPIC_API_KEY` and a supported `BRANDWRIGHT_MODEL_NAME` before opting in. No model call occurs when no approved source is retrieved.

To opt into Claude in PowerShell (after installing dependencies and confirming your organisation permits external processing):

```powershell
$env:BRANDWRIGHT_MODEL_MODE = "claude"
$env:BRANDWRIGHT_ANTHROPIC_API_KEY = "YOUR_API_KEY"
$env:BRANDWRIGHT_MODEL_NAME = "claude-sonnet-4-5"
# Submit a review with local_only=false; local_only=true remains the default.
```
- External requests are redacted before dispatch (email, phone, Aadhaar, PAN, IP address, Luhn-valid payment-card candidates, API-key-like strings, title/sign-off names, and caller-supplied confidential strings). The redactor preserves character offsets and performs a second egress scan; a failed scan blocks the call. The AI-use log stores metadata/counts only, never content or redacted values.
- The default request setting is local-only. Set `local_only=false` on an individual review only when external processing is permitted by your organisation's privacy policy.
- Retrieval is still the deterministic in-memory lexical adapter. A production pgvector embedding adapter remains to be connected to the shared knowledge-base schema.
- Clarification drafts are persisted but never auto-approved.
- Uploaded source bytes are not retained; extracted text and spans are stored for local review history.
- Image review includes deterministic palette sampling, configured contrast, alt-text presence, and logo size checks when the caller supplies logo bounds. Automatic logo localization and vision-model analysis are not implemented.

See [`docs/api-contract.md`](docs/api-contract.md) for request and response contracts.
