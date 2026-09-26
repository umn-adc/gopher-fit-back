# Deployment and operations

Run one SQLite database on persistent local storage, with a process supervisor,
HTTPS reverse proxy, and Python 3.13. Install `uv sync --locked`, create a fresh
backup of an existing database, run `uv run alembic upgrade head`, and then start
the API. The application does not migrate on startup. Never run the old Go writer
concurrently. A staging rehearsal against a copy of the real DB is still required;
repository verification uses disposable fixtures, not production data.

Example with a loopback reverse proxy:

```sh
uv run uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 3000 --workers 2 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-access-log
```

Keep the service account's DB directory and backups private. Do not put SQLite
on NFS/network shares or share the file between hosts. Multiple local workers
share auth state and rate counters correctly, but SQLite serializes writers.
Rate limiting itself writes to SQLite; monitor lock pressure and provision an
edge rate limiter against distributed abuse. Moving to multiple application
hosts requires a deliberately designed shared database/rate-limit backend; that
is not provided by this SQLite implementation.

## Configuration

`.env` is loaded from the working directory; environment values override it.
Keep secrets outside version control. `.env.example` contains all settings.

| Variable | Default | Purpose |
|---|---|---|
| `JWT_SECRET` | Required, min 32 characters | Random signing and rate-key secret |
| `DATABASE_URL` | `sqlite:///./gopherfit.db` | Use an absolute path, e.g. `sqlite:////srv/gopher/data/gopherfit.db` |
| `JWT_TTL_SECONDS` | 900 | Access lifetime, 1–3600 seconds |
| `REFRESH_TTL_SECONDS` | 2592000 | Absolute session lifetime in seconds |
| `RECOVERY_ENABLED` | false | Enable enrollment and reset only when SMTP/frontend are ready |
| `RECOVERY_TTL_SECONDS` | 1800 | Verification/reset lifetime; maximum 86400 seconds |
| `RECOVERY_FRONTEND_URL` | Empty | HTTPS page, without query/fragment/credentials |
| `SMTP_HOST`, `SMTP_FROM` | Empty | Required when recovery enabled |
| `SMTP_PORT`, `SMTP_TLS` | 587, `starttls` | `starttls` or `implicit` (usually port 465); TLS certificate verification required |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Empty | Provider credentials when needed; unauthenticated relay must enforce its own restrictions |
| `SMTP_TIMEOUT_SECONDS` | 10 | Socket timeout, up to 60 seconds |
| `AUTH_RATE_LIMIT` | 20 | Requests per client IP per window, shared across `/auth/*` except recovery and `/profile/password` |
| `RECOVERY_RATE_LIMIT` | 5 | Separate IP bucket across all `/auth/recovery*` operations |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | Fixed-window duration for both buckets |
| `METRICS_TOKEN` | Unset (disabled) | Independent secret, at least 32 characters; used as Bearer token |
| `CORS_ORIGINS` | `[]` | JSON list, e.g. `["https://fit.example.com"]`; exact origins, no paths/trailing slash/wildcard |
| `BACKUP_DIRECTORY` | `./backups` | Snapshot destination for backup CLI |
| `BACKUP_RETENTION` | 7 | Number of successful snapshots retained per source path; minimum 1 |

Old stateless JWTs are intentionally rejected. Keep a consistent JWT secret
across workers and coordinate frontend login/refresh rollout. A secret change
invalidates access JWTs, but **does not revoke opaque refresh tokens**; use
session revocation as well if responding to a credential compromise. Password
changes/resets and the logout endpoints already revoke their relevant sessions.

## Recovery delivery and frontend requirements

A production deployment needs a real SMTP provider or controlled relay, DNS/mail
configuration required by that provider, and the HTTPS frontend recovery page.
No emails were sent during repository work; tests replace SMTP with fakes.
There is no development mail sink disguised as production delivery.

Users enroll their own recovery email with password confirmation, then verify it.
Original username-only users are not recoverable until that enrollment succeeds.
The backend emails links whose secrets are in URL fragments; the frontend posts
them in JSON, strips fragments immediately, avoids third-party scripts/analytics,
and never logs them. Serve this page with a restrictive referrer policy and CSP.

SMTP runs after DB commit as an in-process background task. Failures increment
metrics and emit a redacted event; 202 means accepted, not delivered. Worker
shutdown/crash can lose a message. Users can retry (a retry invalidates the prior
challenge); there is **no durable queue or guaranteed delivery**. If business
requirements need delivery guarantees, add an external queue/provider integration
with encrypted transient payloads and operational retry/dead-letter handling.
The database currently stores hashes only and cannot reconstruct lost messages.
A sufficiently capable SMTP relay and monitoring are still external setup work.

## Limits, proxies, CORS, and request logs

Counters are committed independently of the request, including failed attempts,
and atomically shared across workers using the same DB. Limits are per effective
client IP, not account, and fixed-window boundaries can allow twice the nominal
limit in a short interval. Shared NAT clients share a budget. The database stores
HMACs of rate keys rather than raw IPs; expired counters are pruned on limiter use.
HTTP 429 includes `Retry-After` seconds and the standard JSON error envelope.
Database limiter failures fail closed with JSON 500. OPTIONS preflights are exempt.

The app never parses forwarded-IP headers itself. Uvicorn can rewrite the peer
address only for proxies listed in `--forwarded-allow-ips`. Restrict direct backend
network access and make the proxy overwrite incoming forwarding headers. Do not
use `*` on an internet-accessible backend. If proxy headers are disabled or a
proxy is not trusted, all its clients share that proxy's rate bucket. If the proxy
chain differs from the example, configure the actual trusted peers explicitly.

CORS allows only configured origins, Bearer/JSON/request-ID headers, and supported
methods, including auth/throttle error responses. The API uses no cookies and does
not allow credentialed CORS. CORS does not replace authentication or authorization.
Set proxy body-size/time limits appropriate to the application (for example 1 MiB)
and use HTTPS for all credential traffic.

Structured JSON application logs contain event, request ID, method, route template,
status, and duration. Errors include exception type and request ID, never SQL
parameters, request bodies, authorization headers, reset secrets, or query strings.
Incoming request IDs are accepted only if they match a bounded safe character set;
otherwise the server generates a UUID. `X-Request-ID` is exposed to CORS clients.
Disable Uvicorn's default access log as shown and configure proxy/APM logs with
similar redaction; external instrumentation can otherwise log sensitive URLs or
bodies. Application logging cannot enforce a proxy/provider's logging policy.

## Probes and metrics

- `/health/live`: public 200, process responding; no DB call.
- `/health/ready`: public 200 only when DB is reachable and the Alembic revision
  matches the repository head; otherwise 503 with `{"error":"Not ready"}`.
  Startup itself fails if migrations are missing, so an unmigrated process will
  not begin serving either probe. Readiness catches later DB/revision problems.
- `/metrics`: 404 if disabled. Otherwise requires a separate `METRICS_TOKEN` Bearer
  credential and returns Prometheus text: HTTP counts/duration totals by method,
  route template/status, plus recovery delivery success/failure counts. Restrict
  it at the network/proxy layer too; a user JWT does not grant metrics access.

Metrics use bounded route labels, are thread-safe and **process-local**, and reset
on restart. With multiple Uvicorn workers, requests can hit different counters;
this endpoint does not claim aggregate multiworker totals. For reliable aggregate
monitoring, expose/scrape separate single-worker instances on distinct ports or
use external proxy/process metrics, or add a multiprocess metrics backend.
Alert on readiness failures, 5xx rates, delivery failures, lock contention, disk
capacity, and the age of the most recent verified off-host backup.

## Backup scheduling and restore rehearsal

The backup CLI uses SQLite's backup API, including committed WAL data. It writes
a mode-0600 temporary file, verifies integrity and foreign keys, fsyncs and
atomically publishes a complete snapshot, then removes old snapshots belonging
to that source DB path. A failed backup does not trigger retention. Output is the
snapshot path; no secrets are printed. Never copy just the main DB file while
writers are active. The first Alembic `.pre-python.bak` is historical and is not
refreshed on every revision; take regular independent snapshots.

```sh
uv run python -m scripts.backup create \
  --database-url sqlite:////srv/gopher/data/gopherfit.db \
  --directory /srv/gopher/backups --keep 14
```

The DB and backup storage must exist on a filesystem supporting atomic hard links
within the backup directory. The CLI creates the destination directory if needed
(mode 0700) and has a 60-second copy deadline. Larger/busy deployments should
measure runtime and adjust the operational backup strategy. Retention is a count,
not days; changing the source path creates a separate retention group. Copy
snapshots to separately configured encrypted off-host storage and monitor that
copy; local snapshots on the same disk are not disaster recovery.

Example daily cron under the service account (adjust paths):

```cron
15 2 * * * cd /srv/gopher/app && /usr/bin/flock -n /srv/gopher/backup.lock /home/gopher/.local/bin/uv run python -m scripts.backup create --directory /srv/gopher/backups --keep 14 >> /srv/gopher/backup.log 2>&1
```

A systemd timer can execute the same command with `WorkingDirectory`,
`EnvironmentFile`, and `User` set for the service. Scheduling is operator setup,
not an installed timer. Test and monitor the schedule and retention policy.

Rehearse before depending on a backup:

```sh
uv run python -m scripts.backup restore /srv/gopher/backups/SELECTED.sqlite3 /srv/gopher/restore/rehearsal.db
DATABASE_URL=sqlite:////srv/gopher/restore/rehearsal.db uv run alembic upgrade head
DATABASE_URL=sqlite:////srv/gopher/restore/rehearsal.db uv run alembic current
DATABASE_URL=sqlite:////srv/gopher/restore/rehearsal.db uv run alembic check
DATABASE_URL=sqlite:////srv/gopher/restore/rehearsal.db RECOVERY_ENABLED=false uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 3001 --no-access-log
```

Restore refuses an existing destination or WAL/SHM sidecars, uses the backup API,
and checks integrity/foreign keys before publishing. It **revokes all restored
sessions and recovery challenges and clears pending email changes**; an older
snapshot must not revive consumed refresh/reset credentials. Users log in again.
The source backup remains unchanged. Original content and verified addresses are
restored; reverting to a snapshot still reverts user/password/deletion history.

Verify `/health/ready`, known login, profiles/meals/workouts/records, and expected
row counts against the selected snapshot. The automated restore test includes
committed WAL data, retention, application login/reads, and auth revocation.
For an actual recovery, stop all writers, preserve the damaged DB and sidecars,
restore to a **new** path, migrate/verify it, point `DATABASE_URL` at that path, then
restart. Avoid copying over a live SQLite file. Restoring loses writes since the
snapshot; reconcile or explicitly accept that loss before cutover.
