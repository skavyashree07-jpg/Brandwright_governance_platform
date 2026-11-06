# Brandwright frontend

A modular Next.js frontend for the Brandwright pre-publication brand-governance platform.

## Stack

- Next.js 16 App Router + React 19 + TypeScript
- Tailwind CSS 4 and the Brandwright component styles in `app/globals.css`
- Radix Tabs, Lucide icons, Framer Motion, and Recharts
- TanStack Query for cached, organisation-keyed governance data
- Zod for client-side sign-in validation
- FastAPI backend through the shared API client: `lib/api.ts`

## Run locally in VS Code

Requirements: Node.js 18.17+ (Node 20 LTS recommended) and npm.

1. Open the repository root in VS Code.
2. Open the integrated terminal in `frontend/`, where `package.json` lives.
3. Install packages:

   ```bash
   npm install
   ```

4. Create `.env.local` from the example:

   **PowerShell**
   ```powershell
   Copy-Item .env.local.example .env.local
   ```

   **macOS / Linux**
   ```bash
   cp .env.local.example .env.local
   ```

5. Confirm the API URL in `.env.local`:

   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```

6. Start the integrated services from the repository root with `docker compose up --build`, or start the backend and its PostgreSQL/MinIO dependencies separately.
7. For frontend-only development, start Next.js:

   ```bash
   npm run dev
   ```

8. Open `http://localhost:3000`.

## Demo accounts

The demo backend seed script creates these accounts (all use `password123`):

| Role | Email |
|---|---|
| Creator | `creator@brandwright.test` |
| Reviewer | `reviewer@brandwright.test` |
| Manager | `manager@brandwright.test` |
| Admin | `admin@brandwright.test` |

The exact permissions are enforced by the backend. The frontend hides routes that are not intended for the signed-in role, but the backend remains the source of truth.

## Routes

| Route | Purpose | Access |
|---|---|---|
| `/` | Public Brandwright landing page based on the supplied HTML design | Public |
| `/login` | Sign in | Public |
| `/workspace` | Create and pre-check content; accept suggestions or dismiss findings | Creator, Admin |
| `/queue` | Review submitted content, comment, approve or request changes | Reviewer, Manager, Admin |
| `/insights` | Guideline health, fact-drift alerts and scorecard | Manager, Admin |

## Backend integration

All HTTP calls, auth headers, API URL configuration and response types are centralised in `lib/api.ts`. Components call `api.*` methods rather than calling `fetch` directly. The shared FastAPI backend serves `/api/v1` and uses the same organisation-scoped PostgreSQL models for content, findings, decisions, and insights.

Current API base path: `/api/v1`.

The frontend redesign preserves the existing routes and API contracts. Governance query keys include the authenticated organisation, and the query cache is cleared on sign-out or an expired session.

The frontend uses these integrated backend endpoints:

- `POST /auth/login`, `GET /auth/me`
- `POST /kb/guidelines`, `GET/PATCH /kb/rules`, `GET/POST/PATCH /kb/facts`, `GET/POST /kb/terms`, `GET/POST /kb/assets`
- `POST /content`, `POST /content/upload`, `GET /content`, `GET /content/{id}`, `GET /content/{id}/versions`, `POST /content/{id}/versions`
- `POST /content/{id}/review`, `GET /content/{id}/findings`, `POST /content/{id}/submit`
- `GET /queue`, `POST /content/{id}/approve`, `POST /content/{id}/request-changes`
- `POST /findings/{id}/decision`
- `GET/POST /content/{id}/comments`, `GET /content/{id}/audit`
- `GET /insights/guideline-health`, `POST /insights/guideline-health/{rule_id}/clarification`, `PATCH /insights/clarifications/{id}`, `GET /alerts/fact-drift`, `PATCH /alerts/{id}`
- `GET /trust/scorecard`, `POST /trust/run`, `GET /insights/overview`

## Important integration notes

- The backend finding serializer returns the latest human `decision` and its reason; all decisions remain in the audit history.
- The backend's `/insights/guideline-health` and `/trust/scorecard` endpoints allow `admin` and `manager`; the insights page is restricted to those roles.
- The trust scorecard stays in its empty state until `POST /trust/run` succeeds. The latest result and timestamp are retained in the current browser tab's session storage; `GET /trust/scorecard` recomputes metrics rather than returning a persisted run.
- The backend's `/queue` endpoint returns items in `in_review` or `needs_recheck`.
- The backend is authoritative for validation, role permissions, blocking findings and state transitions. Client-side disabled buttons are only usability guidance.
- The login token is stored in `localStorage` for this prototype. For production, prefer an httpOnly, Secure, SameSite cookie and a CSRF strategy.
- The landing page is a product/marketing page; the authenticated workspace is a separate application shell.

## Checks

```bash
npm run typecheck
npm run build
```

## Project structure

```text
app/
  page.tsx                 # Public landing page
  login/page.tsx           # Authentication
  workspace/page.tsx       # Creator workspace
  queue/page.tsx           # Human review queue
  insights/page.tsx        # Governance insights
  globals.css              # Tailwind import and shared design system
components/
  Shell.tsx                # Auth/session/role-aware navigation and workspace shell
  Providers.tsx            # Browser query client provider
  Annotated.tsx            # Span-highlighted review content
lib/
  api.ts                   # Typed API client and backend contract
  kb.ts                    # Guideline/fact source labels
```

## Visual assets and workspace layout

The public landing page uses the three supplied image assets in `public/images/`:
- `ai-human-interface.jpeg` — hero image beside the main platform message.
- `ai-platform-illustration.jpeg` — connected AI workflow section.
- `security-key-illustration.jpeg` — responsible governance/security section.

The authenticated workspace uses a left navigation rail and a persistent right-side context column for System Telemetry and Requires Attention. Telemetry labels show only the authenticated API/session state and role; the demo API does not expose latency or worker-queue metrics, so those values are intentionally not fabricated. The context column collapses below the main content on tablet/mobile screens.
