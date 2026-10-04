.PHONY: install run test coverage lint format typecheck quality

install:
	poetry install

run:
	poetry run uvicorn app.main:app --reload --port 8000

test:
	poetry run pytest

coverage:
	poetry run pytest --cov=app --cov-report=term-missing --cov-report=xml

lint:
	poetry run ruff check .

format:
	poetry run ruff format .

typecheck:
	poetry run mypy app

quality: lint typecheck coverage
