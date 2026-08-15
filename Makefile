.PHONY: test lint fmt db docker-db run web web-build e2e up

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src tests

fmt:
	.venv/bin/ruff format src tests

db:
	.venv/bin/python -c "from foodbrew.db import create_database; print(create_database('data/foodbrew.db'))"

docker-db:
	docker compose run --rm foodbrew python -c "from foodbrew.db import ensure_database; print(ensure_database('/data/foodbrew.db'))"

run:
	.venv/bin/uvicorn foodbrew.api.app:app --reload

web:
	cd web && npm run dev

web-build:
	cd web && npm run build

e2e:
	cd web && npm run e2e

up:
	docker compose up --build
