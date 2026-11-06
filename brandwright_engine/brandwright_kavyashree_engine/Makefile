.PHONY: install run test migration
install:
	python -m pip install -r requirements-api.txt
run:
	PYTHONPATH=backend python -m uvicorn app.review.api_service.main:app --reload --app-dir backend
test:
	PYTHONPATH=backend python -m pytest -q tests/kavyashree tests/kavyashree_api
migration:
	cd backend && alembic upgrade head
