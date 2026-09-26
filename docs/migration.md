# Go to Python migration

## Assessment and implementation sequence

The original application used Go `net/http`, handwritten SQL, SQLite, bcrypt,
and HS256 JWTs. Its five feature areas exposed 37 method/path pairs. The existing
tests exercised registration rollback, legacy password migration, JWT failures,
public-profile privacy, meal ownership, workout record maintenance, friendship
state transitions, and dense-rank/percentile behavior.

The migration was implemented in stages: record the route inventory and schema;
add configuration/session/error handling and schema adoption; port auth and
profiles; port nutrition; port transactional workouts and social rankings;
port and extend behavioral tests; compare against the Go server; update setup
and documentation. Original code and tests remain at `legacy/go/`.

| Feature | Existing tables |
|---|---|
| Auth | `users` |
| Profile | `profiles` and identity fields in `users` |
| Nutrition | `meals`, `meal_items`, `macro_goals` |
| Workouts | `workouts`, `workout_item`, `personal_records` |
| Social | `friendships`; reads users and personal records for rankings |

The old `schema_migrations` ledger recorded initial schema creation (1), password
BLOB conversion (2), and personal-record backfill (3). Alembic maintains a separate
`alembic_version` table and leaves that historical ledger untouched.

## Adoption behavior

`0001_adopt_sqlite` is an online, additive baseline. It inspects existing columns,
rejects unknown Go migration versions and foreign-key violations, creates only
missing application tables/indexes, and backfills personal records only when
the table did not already exist. IDs, original workout names/weights, JSON
profile fields, password hashes, relationships, and SQLite autoincrement
sequences are retained. Existing record rows are not recomputed on adoption.

Backfill excludes null/blank exercise names and nonpositive/nonfinite weights.
It uses the same Unicode normalization and stable tie-breaking as Go. The
migration contains its own frozen schema and normalization code so future
application edits cannot change historical migrations. DDL, backfill, and the
revision stamp are transactional.

An old TEXT password column can remain TEXT. SQLite permits BLOB values in it;
new hashes are BLOBs and both old TEXT and BLOB hashes authenticate. Avoiding a
column rebuild removes the need to drop the users table or suspend foreign-key
enforcement. No password reset is required.

## Deployment checklist

1. Install Python 3.13 and run `uv sync --locked`. Keep the existing deployment
   artifact and an independently verified backup for rollback.
2. Copy the actual database to a staging location using SQLite's backup API or
   the `sqlite3` CLI `.backup` command. Include WAL data; do not copy only the main
   file while the old process is writing. Test migration and login on this copy.
3. Schedule the switch, stop the Go server and other writers, and retain the
   deployment secrets. Set an absolute `DATABASE_URL` for the existing database.
   All stateless JWTs require a fresh login after revision 0002.
4. Run `uv run alembic upgrade head`. Before migration, the command creates
   `<database>.pre-python.bak` with SQLite's backup API if none exists. Also create
   a fresh backup with `scripts.backup` before later upgrades. It never overwrites that
   backup. This is a migration snapshot, not a substitute for ongoing backups.
5. Check `uv run alembic current`, inspect `PRAGMA foreign_key_check`, and verify
   row counts, a known login, private profile, meals, and personal records.
6. Start `uv run uvicorn app.main:create_app --factory --host localhost --port 3000`
   from this repository. Configure your existing proxy/process manager to run
   this command instead of Go. Adjust the bind address explicitly if needed.
7. Verify a fresh login and refresh, confirm old JWTs return 401, check readiness,
   and monitor errors before resuming normal traffic.

The application never migrates during server startup. Startup fails with an
actionable message unless the database revision matches the available Alembic
head. This avoids schema work racing across multiple server processes.

If adoption finds missing columns, unknown migration versions, or orphaned rows,
it stops without changing existing data. Inspect and repair a copy according to
the deployment's actual data history, then retry; it does not silently delete
invalid rows. The repository contains no production database, so validation
against the deployment's own copy remains an operator step.

## Rollback and future schema work

The baseline downgrade intentionally refuses destructive operations. Before the
new server accepts writes, rollback means stopping it and restoring the verified
pre-switch database with the previous application. After it accepts writes,
restoring an older snapshot loses those newer writes; reconcile them before any
rollback. Do not run both backends as writers during the cutover.

Do not use `alembic stamp head` to bypass adoption or run the archived Go
auto-migrator against a new Python database. Alembic and the old Go migration
ledger have different ownership. For future changes, add a reviewed revision.
The models retain SQLite REAL types and primary-key metadata; Alembic comparison
also recognizes supported TEXT hashes, ignores the historical Go ledger, and
checks actual inline foreign keys to avoid unnecessary table rebuilds. Run
`uv run alembic check` to check model/schema agreement, and review generated
operations before applying any future migration.

## Revision 0002: remaining backend gaps

`0002_backend_lifecycle` follows the frozen adoption revision without editing it.
It adds `workouts.occurred_at TEXT NULL`, storing fixed-width UTC ISO timestamps,
and leaves every existing workout time NULL. It never infers dates from IDs,
other rows, or migration time. Existing values, password hashes, IDs, sequences,
record sources, relationship rows, and the Go migration ledger are preserved.

New tables are `auth_sessions`, `refresh_tokens`, `recovery_addresses`,
`recovery_tokens`, and `rate_buckets`. All user-owned security tables have
cascading foreign keys; no address is invented for existing users. Refresh and
recovery tokens are stored only as hashes. The users table does not change.

Indexes support the actual queries:

- `workouts(user_id, occurred_at, id)` for chronological pages/ranges; existing
  `workout_item(workout_id)` for batched children.
- `meals(user_id, id)` and `meal_items(meal_id)` for owned pages/child batches.
- Friendship participant/status indexes for both sides of the OR ownership
  filter; actor index for cascading account cleanup. Pair ordering remains stable.
- Session user and refresh session indexes for revocation and cascade cleanup;
  recovery user/purpose for invalidation; rate expiry for bounded-window pruning.
- Existing `personal_records(exercise_key, max_weight DESC, user_id)` remains
  the ranking index. Ranking windows run before LIMIT/OFFSET.

Upgrade a stopped deployment only after rehearsing on a fresh backup copy:

```sh
uv sync --locked
uv run python -m scripts.backup create --directory /srv/gopher/backups --keep 14
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

The backup command requires an existing DB; skip it for a new empty installation.
Use `DATABASE_URL` to point each command at the intended copy/file. Configuration
is listed in [deployment](deployment.md). No command was run against production
as part of repository verification. Tests exercise populated legacy and 0001
upgrades, foreign keys, preservation, and rollback of a partially applied 0002
DDL failure. `alembic check` is also exercised on temporary fresh/legacy databases.
Both downgrades intentionally refuse destructive changes; follow the tested
restore procedure instead. Restoring an earlier snapshot loses later writes and
can resurrect deleted accounts/old passwords; assess that impact before cutover.

Schema compatibility does not imply API compatibility: the archived Go comparison
script describes the initial Python baseline. Revision 0002 deliberately changes
JWT acceptance, validation, nested writes, pagination, and workout ordering; see
[API changes](api.md). Do not use the old Go service as a writer on an upgraded DB.
