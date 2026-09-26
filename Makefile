.PHONY: setup migrate dev test check legacy-check openapi backup

setup:
	uv sync --locked

migrate:
	uv run alembic upgrade head

dev:
	uv run uvicorn app.main:create_app --factory --host localhost --port 3000 --reload --no-access-log

test:
	uv run pytest -q

check:
	uv run ruff check app migrations tests scripts
	uv run ruff format --check app migrations tests scripts
	uv run mypy
	uv run pytest -q
	uv run python -m scripts.export_openapi --check

openapi:
	uv run python -m scripts.export_openapi

backup:
	uv run python -m scripts.backup create

legacy-check:
	cd legacy/go && go test ./... && go vet ./...
