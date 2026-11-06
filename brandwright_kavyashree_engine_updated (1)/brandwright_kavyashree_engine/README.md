# Brandwright — Kavyashree's AI & Review Engine

Ready-to-integrate modules for ingestion, deterministic rules, retrieval-grounded AI review,
claims verification, intent lock, privacy redaction, trust evaluation, and guideline drafting.

The original engine remains framework-neutral and uses plain dictionaries/dataclasses at module boundaries. A separate FastAPI + SQLAlchemy adapter is included under `backend/app/review/api_service/`. It uses isolated `review_engine_*` tables for local development and must be mounted behind the shared app authentication and organisation-scope controls before deployment.

## API backend

See [`README_API.md`](README_API.md) for setup, run commands, database configuration, API docs and integration boundaries.

## Install
Merge `requirements-kavyashree.txt` into the backend requirements and install it.
For OCR, install the Tesseract executable separately and ensure it is on PATH.

## Tests
From the project root:
`$env:PYTHONPATH = "backend"; python -m pytest -q tests/kavyashree tests/kavyashree_api`

## AI provider
Mock mode is the default. An optional Anthropic Claude adapter is included; configure the API key and model in `.env`, then set `local_only=false` for reviews approved for external processing. The live provider has not been exercised in this build environment. pgvector retrieval, authentication/RBAC, organisation scoping and background jobs remain shared-backend integration work.

## Demo
`python -m app.review.demo`
