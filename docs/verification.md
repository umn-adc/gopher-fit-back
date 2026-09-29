# Verification and the reported pytest stall

Before implementation, `uv run pytest -vv -x -o faulthandler_timeout=15` completed
all **182 existing tests in 14.49 seconds**, including the first registration test.
The same tests passed after the intentional contract updates (182 in 24.24 seconds).
No tests were skipped or marked xfail, and the TestClient, real SQLite transactions,
foreign keys, and migration checks were retained. New tests extend these checks.

The first-test path was inspected: temporary DB migration/backup, SQLite session
creation, TestClient lifespan startup, and the AnyIO blocking portal. Migration
backup happens before opening the migration write transaction, test databases are
isolated, and startup only checks the Alembic revision. No blocked stack trace or
stall occurred in this checkout. The environment at the initial run was Python
3.13.14, pytest 9.1.1, FastAPI 0.141.1, Starlette 1.7.0, AnyIO 4.15.1,
SQLAlchemy 2.0.54, httpx 0.28.1, and httpx2 2.13.1. Starlette's installed TestClient
prefers httpx2; both were already in the supplied lockfile/environment. No test
transport or dependency downgrade was used to bypass the report. The only added
packages are email-validator and its dnspython dependency.

There is **insufficient evidence to attribute the earlier stall to a specific
cause**. It is not a currently reproduced backend failure. The original stalled
process traceback/environment would be needed to diagnose that prior occurrence;
claiming a dependency or deadlock fix would be speculative. Pytest now has a
30-second faulthandler diagnostic timer (it prints stacks and does not skip,
terminate, or change tests). If it recurs, capture:

```sh
uv sync --locked
uv run pytest -vv -s --setup-show -o faulthandler_timeout=15 tests/test_auth_profile.py::test_registration_login_and_private_public_contracts
uv pip list
```

Preserve the emitted stacks and exact environment. A TestClient startup/portal
wait, SQLite writer wait, or backup progress wait requires a different fix;
do not remove transactions, bypass lifespan, or silence a test to get past it.

## Coverage added

- Verified-email enrollment, username recovery, uniform responses, expiration,
  replacement/single-use/purpose-bound hashed tokens, no token logging, and SMTP
  failures/rollback without real email.
- Refresh rotation, committed reuse revocation, concurrent duplicate refresh,
  expiration, logout/all, password-change/reset revocation, deletion cascades,
  unrelated-account preservation and rollback after a cascade fails.
- Shared create/update validation, UTF-8 bcrypt byte limits, meal dates/times,
  profile limits, nested-list ownership and late-write/record rollback.
- Timezone conversion, unknown workout dates, chronological ties, range filtering,
  bounded pages, batched child query counts, global ranks/percentiles.
- Populated legacy and 0001 migrations, unknown dates, DDL-failure rollback, row,
  hash and record preservation, and Alembic schema agreement.
- Shared/concurrent rate limits and forwarded-header behavior, liveness/readiness,
  protected metrics, request IDs, redacted structured logs, and CORS.
- SQLite WAL backups, retention, failed snapshot handling, safe restore, integrity,
  foreign keys, restored application reads and credential invalidation.

`make check` runs Ruff lint, Ruff formatting, strict mypy (app plus new operational
scripts), pytest, and OpenAPI snapshot comparison. Tests do not use production
storage or send actual mail. Deployment SMTP, a separately hosted frontend,
off-host backup replication, scheduling, and proxy configuration still need an
operator's staging verification.

## Recorded final checks

On 2026-09-25, `uv sync --locked` and `make check` completed successfully:

- Pytest: **264 passed in 30.76 seconds** (82 more tests than the supplied suite).
- Ruff lint: passed; formatting: **65 files already formatted**.
- Strict mypy: **no issues in 48 source files**.
- Generated OpenAPI snapshot comparison: passed.
- Backup/restore CLI smoke test on disposable files: passed, including restored
  integrity/foreign keys and `alembic check` with no schema changes detected.
- `git diff --check`: passed. The original frozen 0001 migration/schema and
  legacy comparison script were byte-compared with the pre-work snapshot and
  remain unchanged. Existing Go-to-Python working-tree changes remain in place.

An intermediate new pagination stress-test fixture collided its own explicit and
SQLite-generated workout IDs; the fixture was corrected to use disjoint ID ranges.
The final full run above passed without skips or xfails.

## Next-steps backend milestones (2026-09-29)

Milestones 2a–2f (OpenAPI accuracy, units, meals by date, weekly target, username
search, favorite meals) were checked after each commit. Final results on `a6ccb88`:

- `make check`: Ruff lint and format passed (77 files), strict mypy found no issues
  in 50 source files, **pytest 323 passed**, OpenAPI snapshot comparison passed.
- `uv run alembic check` against a temporary database upgraded to
  `0006_favorite_meals`: no new upgrade operations detected. Every revision was
  also upgraded from populated legacy Go and 0002 databases in tests.
- `tests/test_openapi_responses.py` validates real responses from the main endpoints
  against the generated document, failing on undocumented keys or statuses.
- The frontend integration suite (`tests/live-api.cjs`) was run against this backend
  before the frontend update: profile/nutrition passed, and the workout section
  failed with `weight_unit (kg or lb) is required when weight is positive`, as D1
  requires. The frontend and backend must be deployed together.

Two full runs during this work each had one unrelated test fail with an unexpected
401. Neither reproduced in 8+ reruns. The host (WSL2) wall clock was measured
stepping back 1.7 seconds within a minute; PyJWT rejects an access token whose
`iat` is later than the current time, so a token minted just before such a step is
briefly rejected. Authentication code was not changed for this; rerun on a host
with a monotonic wall clock if it recurs.
