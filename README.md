# Gopher Fit Backend

Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, and SQLite. The uncommitted
Go-to-Python migration is retained, with the original Go source at `legacy/go/`.
Feature code keeps the router → service → repository boundaries.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv python install 3.13
uv sync --locked
cp .env.example .env
# Set JWT_SECRET to a random secret of at least 32 characters.
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --host localhost --port 3000 --reload --no-access-log
```

Windows: use `Copy-Item .env.example .env`. `.env` is read automatically and
process environment values take precedence. SQLite is the supported database;
use an absolute `DATABASE_URL` in deployment.

Swagger UI: `/swagger/index.html`. OpenAPI: `/swagger/doc.json`, with a checked-in
snapshot at [docs/openapi.json](docs/openapi.json). Health probes are `/health/live`
and `/health/ready`. Feature routes require `Authorization: Bearer <token>`.

The new authentication contract requires a fresh login after upgrading:
stateless Go/initial-Python JWTs are rejected. Login/register retain `token`,
`user_id`, and `username` and add rotating `refresh_token`, `expires_in`, and
`token_type`. Password changes/reset and logout revoke sessions immediately.
Read [API and frontend changes](docs/api.md) before updating callers.

Account recovery is **disabled by default**. Accounts originally had only a
username and password, so users must enroll and verify a recovery email while
signed in. Configure a real SMTP service with TLS and an HTTPS recovery frontend
before enabling recovery. There is no token-returning API, console mailer, or
plaintext token outbox. This repository does not configure a mail provider or
implement the frontend recovery page.

## Verification

```sh
uv run pytest -q
uv run ruff check app migrations tests scripts
uv run ruff format --check app migrations tests scripts
uv run mypy
uv run python -m scripts.export_openapi --check
```

`make check` runs all checks. Tests use temporary databases, real migrations and
transactions, and fake SMTP delivery. They do not open the configured app database
or send mail. [Verification notes](docs/verification.md) record the stall
investigation and checks. Refresh the contract after route/schema edits:

```sh
uv run python -m scripts.export_openapi
```

## Existing databases and operations

Read [migrations](docs/migration.md) and [deployment](docs/deployment.md). Keep
other writers stopped during migration. `0002_backend_lifecycle` adds nullable
workout timestamps, authentication/recovery/rate-limit tables, and indexes. It
preserves existing rows and leaves historical workout times unknown. Startup
requires the current migration head; it never applies migrations automatically.

Create a consistent backup and rehearse restoring to a new file:

```sh
uv run python -m scripts.backup create --directory ./backups --keep 7
uv run python -m scripts.backup restore ./backups/SELECTED.sqlite3 ./restored.db
```

Backups include committed WAL data via SQLite's backup API, verify integrity and
foreign keys, and publish only complete snapshots. See deployment documentation
for scheduling, retention, access controls, and restore/cutover instructions.
Local snapshots require separately configured off-host backup storage.

[Architecture](docs/architecture.md) describes module boundaries. Archived Go
checks remain available with `make legacy-check` (Go 1.24+). The original
`scripts.verify_legacy` comparison targets the initial Python compatibility
baseline and is retained as historical tooling; it intentionally does not certify
the new JWT, validation, timestamp, nested-write, or pagination contracts.
