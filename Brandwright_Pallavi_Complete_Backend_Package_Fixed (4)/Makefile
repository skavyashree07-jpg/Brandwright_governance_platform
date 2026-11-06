.PHONY: build up down restart logs test migrate seed clean

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart: down up

logs:
	docker-compose logs -f backend

test:
	docker-compose exec backend pytest

migrate:
	docker-compose exec backend alembic upgrade head

seed:
	docker-compose exec backend python seed.py

clean:
	docker-compose down -v
