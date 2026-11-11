# Brandwright API Contract & Data Specifications

## Jury demo authentication

Set the backend-only `JURY_DEMO_ENABLED=true` to enable public jury access. The endpoint issues a JWT for the seeded Admin user in the fictional `Brandwright Demo` organisation; no personal credentials are accepted or returned.
For registered-user password login, keep `DEMO_MODE=false`; the local sample environment may enable the existing demo credential shortcut.

- `POST /auth/jury-demo-login` — start a jury demo session. Returns the normal bearer-token response.
- `POST /auth/jury-switch-role` — authenticated jury sessions only; body is `{"role":"admin"|"reviewer"|"creator"}`. Returns a replacement JWT for the matching seeded demo user while preserving the jury session identifier and expiry.
- `GET /auth/me` — includes `jury_demo: true` for a jury session.

Jury role switching is authorized by a signed session claim and constrained to the seeded demo organisation. Other login tokens cannot call the role-switch endpoint. Disable the feature by setting `JURY_DEMO_ENABLED=false`; existing jury JWTs are rejected while it is disabled. Normal authentication and `/auth/demo-login` remain separate.

All API endpoints are prefixed with `/api/v1` and require JSON bodies and JWT Bearer authorization unless noted otherwise.
