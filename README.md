# Brandwright

Brandwright is a pre-publication brand-governance platform. Creators submit text or supported files for checks against approved brand guidelines and facts. The system returns source-linked findings and suggested wording; people retain control over decisions and approvals.

## Features

- **AI-assisted content review:** deterministic checks, claim verification and retrieval-grounded LLM findings. Findings must refer to an approved source; unsupported results are not presented as verified violations.
- **Human review and accountability:** role-based creator/reviewer/admin access, finding decisions, comments, approval or change requests, and audit history.
- **Versioned content and brand knowledge:** immutable content versions, guideline rules, facts, preferred/banned terms and uploaded assets.
- **Governance monitoring:** fact-drift alerts, guideline-health insights and a trust scorecard/evaluation workflow.
- **Demo experience:** seeded fictional Brandwright organisation with creator, reviewer and admin demo roles. Jury role switching is separately controlled by configuration.

## Technology

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, TanStack Query.
- Backend: FastAPI, SQLAlchemy, Alembic and Pydantic.
- Data/services: PostgreSQL with pgvector, Redis/RQ and S3-compatible RustFS storage.
- AI: mock review provider by default; optional Anthropic Claude integration.
- Local orchestration: Docker Compose.

## Requirements

For the recommended full-stack setup:

- Docker Desktop with Docker Compose v2
- Git

For running parts outside Docker:

- Node.js 20 LTS and npm (frontend)
- Python 3.11 and PostgreSQL/pgvector (backend)
- Redis and an S3-compatible storage service (for the full backend feature set)

## Run the complete application locally

1. Clone the repository and enter its root directory:

   ```bash
   git clone https://github.com/skavyashree07-jpg/Brandwright_governance_platform.git
   cd Brandwright_governance_platform
   ```

2. Create the root environment file:

   **PowerShell**
   ```powershell
   Copy-Item .env.example .env
   ```

   **macOS/Linux**
   ```bash
   cp .env.example .env
   ```

3. Open `.env` and replace the placeholder database, storage and secret values. Use a long, random `SECRET_KEY` (at least 32 characters). Do not commit the populated `.env` file.

4. Build and start the stack:

   ```bash
   docker compose up --build
   ```

   The first run downloads images, installs dependencies, applies backend migrations and runs the seed script. This can take several minutes.

5. Open:
   - Frontend: http://localhost:3000
   - Backend health: http://localhost:8000/health
   - API documentation: http://localhost:8000/docs
   - RustFS console: http://localhost:9001

6. Use the **Try the demo** flow on the sign-in page. The seed creates demo accounts for creator, reviewer and admin roles. Demo sign-in is enabled only when `DEMO_MODE=true`. The demo uses fictional sample data; do not put real confidential information into it.

To stop the services, press Ctrl+C and run `docker compose down`. To also delete the local database and object-storage data, run `docker compose down -v` (this is destructive).

Useful operations:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f frontend
docker compose restart backend
```

## Configuration

The root `.env.example` documents the variables consumed by Docker Compose.

| Variable | Purpose |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL database credentials/name |
| `SECRET_KEY` | JWT signing secret; set a strong private value |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | RustFS/S3-compatible storage credentials |
| `CORS_ORIGINS` | Allowed browser origins; local default is `http://localhost:3000` |
| `DEMO_MODE` | Enables the demo sign-in endpoint; keep disabled for non-demo deployments |
| `JURY_DEMO_ENABLED` | Enables the separate jury demo session and role-switch endpoint |
| `BRANDWRIGHT_MODEL_MODE` | `mock` (default) or `claude` |
| `BRANDWRIGHT_ANTHROPIC_API_KEY` | Anthropic API key when using Claude mode |
| `REVIEW_ASYNC` | Enables queued review processing through Redis/RQ when set to `true` |
| `REVIEW_JOB_TIMEOUT_SECONDS` | Worker job timeout in seconds |

Mock mode is suitable for local evaluation and does not require an external model key. To enable Claude, set `BRANDWRIGHT_MODEL_MODE=claude` and provide `BRANDWRIGHT_ANTHROPIC_API_KEY` in the backend environment, then recreate the backend container. External model use may incur provider charges.

The frontend Docker build uses `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` for the browser-facing local API. For a standalone frontend, copy `frontend/.env.local.example` to `frontend/.env.local` and set `NEXT_PUBLIC_API_URL` to the reachable backend URL.

## Roles and main journey

1. A creator signs in, creates a content item, enters its intent and content, then runs a review.
2. The review combines deterministic checks, approved-source claim checks and AI review when enabled. Findings include the available source explanation and a proposed fix; AI does not approve or rewrite content automatically.
3. The creator resolves required high-severity or unverifiable findings and submits the reviewed version.
4. A reviewer opens the review queue, examines findings and comments, then approves or requests changes. Manager/admin permissions are enforced by the API.
5. Content details expose version history and the audit timeline. Knowledge and governance screens provide guideline/fact management and monitoring.

The backend is authoritative for organisation scoping, input validation, role permissions and workflow transitions. UI restrictions are not a substitute for API authorization.

## Run frontend checks

```bash
cd frontend
npm ci
npm run typecheck
npm test
npm run build
```

For frontend development, create `frontend/.env.local` from `frontend/.env.local.example`, ensure the API URL points to a running backend, then run:

```bash
npm run dev
```

Open http://localhost:3000.

## Run backend checks

With the backend dependencies installed and the working directory set to `backend/`:

```bash
pip install -r requirements.txt
pytest
```

Some database integration tests are intentionally skipped unless `TEST_DATABASE_URL` points to a disposable PostgreSQL database with the pgvector extension available. For example, set that variable to a dedicated test database before running the suite. Do not point tests at production or valuable local data.

For local API development, start PostgreSQL/pgvector, Redis and RustFS, configure the backend environment from the root `.env.example`, then run:

```bash
alembic upgrade head
python seed.py
uvicorn app.main:app --reload --port 8000
```

The backend Docker image performs migrations and seeding at container startup. Avoid running multiple seed processes concurrently against the same database.

## Repository layout

```text
backend/
  app/                 FastAPI routes, models, workflow, review and trust logic
  migrations/          Alembic database migrations
  tests/               Backend tests
  seed.py              Idempotent fictional demo-data setup
frontend/
  app/                 Next.js routes
  components/          Workspace and product UI
  lib/                 API client and frontend utilities
docker-compose.yml     Local multi-service stack
.env.example           Root environment template
```

## Troubleshooting

- **Backend does not become healthy:** run `docker compose ps` and `docker compose logs backend postgres`. Check database credentials and wait for PostgreSQL health.
- **Frontend cannot reach the API:** verify `NEXT_PUBLIC_API_URL` and that port 8000 is reachable from the browser. The browser must use a browser-accessible URL, not the internal Compose service name.
- **Uploads/storage fail:** check RustFS is running and that the MINIO credentials in `.env` match the backend environment.
- **Queued reviews remain pending:** check Redis and the worker logs. Set `REVIEW_ASYNC=true` only when the worker service is running.
- **Claude review is unavailable:** confirm model mode, API key and provider access. Mock mode is the no-key fallback.
- **Port already in use:** stop the process using the port or change the host-side port mapping in `docker-compose.yml`.

## Security notes

This repository is a prototype/demo application. Use fictional data for demonstrations. Keep secrets out of source control, disable demo and jury login in non-demo environments, configure restrictive CORS origins, and use production-grade authentication/session and storage settings before exposing a deployment to real users.
