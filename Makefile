.PHONY: help install run dev test lint format migrate migrate-up migrate-down docker-up docker-down docker-logs seed

help:
	@echo "Available targets: install run dev test lint format migrate migrate-up docker-up docker-down seed"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

test:
	pytest -v

lint:
	ruff check app tests
	black --check app tests

format:
	ruff check --fix app tests
	black app tests

migrate:
	alembic revision --autogenerate -m "$(m)"

migrate-up:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

seed:
	python -m scripts.seed_data
