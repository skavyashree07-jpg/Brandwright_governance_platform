You are helping build "Brandwright", a pre-publication brand-governance platform for a hackathon (Inkloom AI problem statement). A creator submits content (text, image, DOCX, PDF) with a one-line intent. The system checks it against the organisation's approved guidelines, facts and assets, explains each finding with the exact source, suggests a fix that preserves the intent, and routes it through a role-based approval workflow. Humans always make the final decision. Team of 3, so keep scope tight and build a working vertical slice first.

TECH STACK
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS
- Backend: FastAPI (Python 3.11), SQLAlchemy + Alembic, Pydantic
- DB: PostgreSQL with pgvector. Queue: Redis + RQ
- Files: S3-compatible storage (MinIO locally)
- LLM: Claude API behind an interface (class LLMClient) with a MOCK mode so nobody is blocked
- Parsing: python-docx, PyMuPDF, Tesseract. Images: Pillow, OpenCV
- Auth: JWT, role-based access (creator, manager, reviewer, admin), organisation-scoped data
- Tests: pytest, Playwright. CI: GitHub Actions. Local: Docker Compose

REPO STRUCTURE (each folder has one owner; do not edit other owners' folders without asking)
/backend/app/api          routes (owner: Pallavi; comments + versions routes: Gousiya)
/backend/app/models       SQLAlchemy models, schemas (Pallavi)
/backend/app/workflow     approval state machine, audit log (Pallavi)
/backend/app/insights     recurring issues, guideline health, fact drift (Pallavi; drafting logic: Kavyashree)
/backend/app/review       ingestion, rule engine, retrieval, LLM review, claims ledger, intent lock, redaction (Kavyashree)
/backend/app/trust        evaluation runner and metrics (Kavyashree)
/backend/tests, /eval     tests; labelled test set (Pallavi creates data, Kavyashree runs it)
/frontend/app, /frontend/components   all screens (Gousiya)
/docs                     API contract, decisions
docker-compose.yml, .env.example, .github/workflows

CORE DATA MODEL
organisations, users(role), guideline_docs, rules(number, text, category, channels[], status, version, sensitivity, embedding), facts(text, owner, source_url, expires_at, version, status, embedding), terms(preferred, banned, notes), assets, content_items, content_versions(version_no, body, intent, channel, status), findings, finding_decisions(action, reason, user_id), comments(span anchor), approvals, audit_log, ai_usage_log(service, purpose, redacted bool), fact_usage(content_version_id, fact_id), alerts(type, ref_id, status), rule_clarifications(rule_id, drafted_text, status).

FINDING SCHEMA (the contract between AI, backend and frontend; do not change without telling the team)
{
  "id": "uuid", "content_id": "uuid", "version_no": 1,
  "span": {"start": 0, "end": 10, "page": null},
  "category": "tone|terminology|messaging|visual|accessibility|claim",
  "severity": "low|medium|high",
  "check_type": "rule|retrieval_ai",
  "status": "violation|cannot_verify",
  "confidence": 0.0-1.0,
  "source": {"type": "rule|fact|asset", "id": "uuid", "clause_text": "..."} or null,
  "explanation": "why this was flagged",
  "suggestion": {"text": "...", "intent_preserved": true} or null,
  "decision": null or {"action": "accept|edit|dismiss", "reason": "..."}
}
A finding with status "violation" MUST have a valid source. If no source supports it, status is "cannot_verify" and it routes to a human.

API CONTRACT (all under /api/v1, JSON, JWT auth)
Auth: POST /auth/login, GET /auth/me
Knowledge base: POST /kb/guidelines (upload), GET /kb/rules, PATCH /kb/rules/{id} (approve/edit), GET/POST/PATCH /kb/facts, GET/POST /kb/terms, GET/POST /kb/assets
Content: POST /content, GET /content/{id}, GET /content/{id}/versions, POST /content/{id}/review, GET /reviews/{id} (status + findings)
Decisions: POST /findings/{id}/decision
Workflow: POST /content/{id}/submit | /approve | /request-changes, GET /queue
Comments: POST/GET /content/{id}/comments
Audit: GET /content/{id}/audit
Insights: GET /insights/recurring, GET /insights/guideline-health, POST /insights/guideline-health/{rule_id}/clarification, PATCH /insights/clarifications/{id}
Fact drift: GET /alerts/fact-drift, PATCH /alerts/{id}
Trust: GET /trust/scorecard, POST /trust/run

THE THREE STANDOUT FEATURES
1. Fact Drift Alerts: when an approved fact is edited or expires, every content version that used it (fact_usage) is re-flagged and an alert is created for the reviewer.
2. Trust Scorecard: runs the labelled test set and shows precision and recall, plus a pipeline trace on each finding (rule engine vs retrieval vs AI, confidence).
3. Guideline Health: rules that are often dismissed or overridden are listed; the AI drafts a clearer wording; the guideline owner approves or rejects it.

NON-NEGOTIABLE PRINCIPLES
- AI never edits content directly; it only proposes. Every accept, edit and dismiss is a human action and is recorded.
- Deterministic rules (banned terms, disclaimers, contrast, alt text) run first and do not depend on the model.
- The LLM only sees retrieved rules/facts and must return the source id it used. Findings without a valid source id are discarded in code.
- Intent Lock: a suggestion that changes the creator's stated intent is rejected before it is shown.
- Redact confidential or personal strings before any external model call; write every external call to ai_usage_log; show which AI services were used on each review.
- Organisation-scoped data everywhere. Never hard-code secrets; use .env.
- Accessible UI: keyboard navigation, contrast, labelled controls, severity never by colour alone.

WORKING RULES
- Build the vertical slice first: guideline in, text + image in, cited findings out, approval recorded. Then the standout features.
- Work in small steps. After each step, run the tests and tell me what changed and how to run it.
- Write pytest tests for backend logic, with at least one test per rule type.
- Use git branches per person (feat/<name>-<topic>) and small commits. Do not rewrite other people's files.
- If something in this brief is ambiguous or conflicts, ask before guessing.
- Demo data is a fictional company only. Never use real confidential material.

Do NOT start coding yet. First confirm you understand this, list any ambiguities, then wait for my role prompt.
