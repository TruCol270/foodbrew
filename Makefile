.PHONY: test lint fmt db docker-db

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src tests

fmt:
	.venv/bin/ruff format src tests

db:
	.venv/bin/python -c "from foodbrew.db import create_database; print(create_database('data/foodbrew.db'))"

docker-db:
	docker compose run --rm foodbrew
