.PHONY: install lint format typecheck test migrate-up migrate-down compose-up compose-down paper-up paper-down

install:
	poetry install

lint:
	poetry run ruff check app tests scripts alembic
	poetry run ruff format --check app tests scripts alembic

format:
	poetry run ruff format app tests scripts alembic

typecheck:
	poetry run mypy --strict app

test:
	poetry run pytest

migrate-up:
	poetry run alembic upgrade head

migrate-down:
	poetry run alembic downgrade base

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v

paper-up:
	docker compose -f docker-compose.paper.yml up --build -d

paper-down:
	docker compose -f docker-compose.paper.yml down -v
