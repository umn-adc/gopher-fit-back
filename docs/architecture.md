# Architecture

The application has six features: auth, profile, nutrition, workouts, social, and
operations.
Each owns its Pydantic schemas, SQLAlchemy mappings, persistence operations,
business rules, and HTTP routes. ORM classes end in `ORM`; API schemas end in
`Request` or `Response`. There are no generic repositories or service bases.

## Boundaries

- `router.py` declares paths, status codes, typed request/response schemas,
  path validation, authentication dependencies, and service construction.
  Endpoints call services and contain no SQL or direct session operations.
- `service.py` enforces ownership and business rules and orchestrates repository
  calls. Services return typed response schemas or `None` and raise domain
  exceptions; they do not import FastAPI or select HTTP status codes.
- `repository.py` contains SQLAlchemy selects, inserts, updates, deletes, and
  flushes. It never commits, rolls back, creates sessions, or returns HTTP
  responses. Database uniqueness errors are translated where their business
  meaning is known.
- `models.py` holds both request/response schemas and ORM models. ORM mappings
  retain the existing SQL names, nullable columns, foreign keys, and constraints.
- `main.py` is the composition root, registering features and exception handlers.
  `core` contains only shared configuration, session lifecycle, domain error
  categories, HTTP ID types, and schema compatibility helpers.

Authentication helpers belong to `auth`. `auth/dependencies.py` exposes the
current user dependency to other routers. `auth/security.py` owns JWT and bcrypt
behavior. `workouts/exercises.py` owns exercise normalization shared with rankings.
Nutrition reuses its Unicode whitespace helper to preserve the Go definition of
a blank name. These modules do not perform persistence or HTTP work.

Registration composes `ProfileService` with `AuthRepository` so user and profile
creation share a transaction. The profile repository also accesses user identity
and password fields. Social rankings read the `PersonalRecordORM` projection
owned and maintained by workouts; social never changes workout data. These are
explicit, limited cross-feature dependencies. No feature imports another router.

## Sessions and transactions

The FastAPI `DatabaseSession` dependency creates exactly one SQLAlchemy session
and transaction for the request. Dependency caching shares it with composed
services/repositories. It commits on success and rolls back on every exception.
Its `scope="function"` makes commit occur before sending the response, so a
failed commit cannot be reported as a successful mutation. Repositories flush
to obtain IDs and detect constraint errors without ending the transaction.

SQLite foreign keys and a 30-second busy timeout are enabled on every connection.
Explicit `BEGIN` makes reads and migration DDL transactional; mutating requests
use `BEGIN IMMEDIATE` before any authorization read. This reserves the SQLite
writer and avoids upgrading an old read snapshot into a write transaction.
Transactions should stay short: no network calls or background work inside them.

Workout creation/deletion, child changes, and recalculation of affected personal
records run together. The service selects the highest positive finite lift per
normalized exercise, breaking ties by lowest item ID. The repository persists
the selected records. Friendship updates/deletes additionally match the previous
actor and status, so a stale state cannot overwrite a block.

The session lifetime follows [FastAPI function-scoped dependency cleanup](https://fastapi.tiangolo.com/advanced/advanced-dependencies/).
Explicit SQLite transaction handling follows [SQLAlchemy's SQLite guidance](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#transactions-with-sqlite-and-the-sqlite3-driver).

## Adding a feature

1. Create `app/features/<name>/` with `__init__.py`, `models.py`, `repository.py`,
   `service.py`, and `router.py`. Use the existing small constructor-injected
   classes and function-based router dependencies as examples.
2. Define typed request/response schemas and any ORM models. Keep request parsing
   in schemas and business validation in the service. Never return an ORM user
   object directly, because it includes a password hash.
3. Put queries in the repository, use-case logic in the service, and dependency
   assembly in the router. Reuse `DatabaseSession` and `CurrentUser`; never create
   a second session inside the feature.
4. Register the router in `main.py`. If the feature is protected, add its prefix
   to the pre-routing authentication list there as well as using `CurrentUser`.
   This preserves authentication before malformed-body handling.
5. Import new ORM models in `migrations/env.py`. Generate an Alembic revision with
   `uv run alembic revision --autogenerate -m "description"`, inspect every
   operation, and test upgrades against an existing populated database. Never
   use `create_all`, `drop_all`, or an unchecked autogenerated table rebuild as
   a runtime migration strategy. Legacy `schema_migrations` is historical data;
   do not remove it just because it is not mapped by the ORM.
6. Add tests covering a meaningful success path, validation/ownership failures,
   and atomicity if multiple writes must succeed together. Tests should assert
   external behavior and persisted state, using `tests/conftest.py` fixtures.
7. Run `make check`, update API documentation, and inspect `/swagger/doc.json`.

For business logic outside HTTP (such as a future CLI), the caller owns
`with Session(engine) as session, session.begin():` and constructs the same
repository/service objects. No alternate persistence framework is needed.

## Session security and operations

Authentication sessions and refresh history live in the auth repository. JWT
validation checks both signed claims and the caller's current database session
inside the request transaction. Refresh rotation and reuse detection serialize
through SQLite's IMMEDIATE writer transaction. Reuse is returned as a failure
value so the router can emit 401 **after committing revocation**; raising a domain
exception here would roll back the revocation. Password mutation composes the auth
repository into ProfileService, using the same session for hash changes and
revocations. Stateless JWT compatibility is intentionally removed.

Recovery is username-based and requires newly enrolled, verified private email.
The service returns an internal `Delivery` with secret fields excluded from repr;
routers schedule SMTP delivery with BackgroundTasks after function-scoped commit.
No raw token enters a persisted outbox, API response, or log. Delivery is best-effort
and can be lost on worker exit; durable delivery requires a separately designed
queue with encrypted payloads, retention, retries, and operator infrastructure.
Never move SMTP inside the SQLite writer transaction.

Operations keeps its own router/service/repository boundary. Health queries and
rate-limit counters use short independent transactions; failed auth still consumes
a counter. Counter rows are shared across workers on the same SQLite database.
Metrics are bounded process-local counters. Core ASGI middleware handles safe
request IDs, request metadata logging, pre-routing signature validation, and
throttles, without holding a database transaction during downstream request work.
The request dependency rechecks live session ownership before any feature access.

New input validation is separate from response models so additive migrations do
not invalidate old rows merely because write constraints become stricter. Parent
pages fetch all children in one query keyed by the page's IDs; a collection read
uses a stable ordering and one consistent request read transaction. Nested-list
replacement and record recalculation share the existing mutation transaction.
