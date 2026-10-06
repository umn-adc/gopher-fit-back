# API and frontend contract

OpenAPI is generated at `/swagger/doc.json`; Swagger UI remains at
`/swagger/index.html`. The exported [OpenAPI snapshot](openapi.json) is verified
by `make check`. All original method/path pairs remain. Responses use
`{"error":"message"}` for errors, including HTTP 400 validation, 401 auth, 404
ownership mismatches, 409 conflicts, 429 throttles, and 503 unavailable recovery.
Unknown fields remain ignored; explicit null scalars are rejected unless documented
as nullable. No 422 `detail` envelope is used. An invalid path or query parameter
returns `Invalid <name>` (for example `Invalid limit`); body errors return `Invalid
JSON` or a specific message. Request IDs appear in `X-Request-ID`.

Each OpenAPI operation declares only the error statuses it can return, all with the
`ErrorResponse` body. 429 (with `Retry-After`) appears only on throttled routes:
`/auth/*`, `/profile/password`, `/social/users/search` and
`/health/connections/{provider}/sync`. Meal and workout responses have typed schemas;
`items` is optional because empty collections are omitted. Registration and profile
PUT list `gender` and `activity_level` as required enums, because the service
rejects any other value with 400 `Invalid profile`. `tests/test_openapi_responses.py`
validates real responses against the generated document, rejecting undocumented
keys and statuses.

## Authentication and account lifecycle

Login/register still return `token`, `user_id`, and `username`, with additions:

```json
{"token":"ACCESS_JWT","user_id":1,"username":"athlete",
 "refresh_token":"OPAQUE_SECRET","expires_in":900,"token_type":"Bearer"}
```

Access tokens are HS256 JWTs containing the legacy `ID` and `Username` plus `sid`,
`type: "access"`, `iat`, and `exp`. They require a live, unrevoked database session.
Default access lifetime is 15 minutes (maximum configured lifetime one hour);
default session/refresh family lifetime is 30 days from login and is not extended
by rotation. **All old stateless JWTs are rejected**, including ones without
expiration. The same JWT secret alone no longer makes old tokens compatible.
Passwords/hashes and user IDs are preserved; users log in again.

| Endpoint | Body/auth | Result |
|---|---|---|
| POST `/auth/register` | Username, password, profile | 201 token pair; atomic user/profile/session creation |
| POST `/auth/login` | `username`, `password` | 200 token pair; unknown user/wrong password both 401 |
| POST `/auth/refresh` | `refresh_token` | 200 new pair; old refresh token consumed |
| POST `/auth/logout` | Bearer access token | 204; revoke that session and its entire refresh family |
| POST `/auth/logout-all` | Bearer access token | 204; revoke all caller sessions |
| DELETE `/auth/account` | Bearer access token, `password` | 204; permanently delete account and owned data |
| PUT `/profile/password` | Bearer access token, `old_password`, `new_password` | Existing success message; revoke all sessions and recovery challenges |

Reusing any consumed refresh token revokes its whole family and returns 401.
This revocation commits even though the request failed. Used token hashes remain
until the session can safely be discarded; access tokens from that session stop
working immediately. Other independent sessions are unaffected by reuse.
Concurrent refreshes of the same token cause reuse revocation: clients must
serialize refreshes, including across tabs. A lost refresh response can require
login again; automatic retries of an old refresh token are unsafe.

Clients should replace the stored pair on refresh, clear both on logout/password
change/reset/deletion, and prompt for login after 401. Treat the refresh token as
a credential. The API returns JSON credentials and uses no cookies: a separately
hosted frontend must explicitly send the Bearer header. Prefer memory storage or
a secure server-side frontend session; long-lived browser storage is exposed to
script compromise. Cookie-based frontend integrations must implement their own
HttpOnly/Secure cookie and CSRF protections.

Deletion requires password confirmation and atomically cascades profiles, meals
and items, macro goals, favorite meals and items, workouts and items, personal records, all friendships
involving the account, sessions/refresh hashes, recovery addresses and challenges.
Unrelated users remain. There is no self-service undelete.

## Recovery enrollment and reset

The existing identity is **username**, not email. A private verified recovery
address is new, optional data, never returned by public profiles. Existing users
have no recovery channel until they enroll. No unverified address can recover an
account, and a reset request cannot supply or change its delivery destination.

1. With Bearer auth, `PUT /auth/recovery-address` with `password` and `email`.
   This returns 202 and emails a verification link. Re-enrollment replaces the
   pending challenge; any existing verified address remains active until the new
   address is verified.
2. The frontend extracts `purpose=verify` and `token` from the **URL fragment**,
   removes it with `history.replaceState`, then submits the token in the JSON
   body to `POST /auth/recovery-address/confirm`. Success is 204. Never put tokens
   in query strings, analytics, error reports, or logs. The frontend must use a
   restrictive referrer policy and avoid third-party code on this page.
3. `POST /auth/recovery/request` with `username` always returns the same 202 body
   for unknown, unenrolled, and enrolled accounts. An enrolled account receives
   a reset link at its verified address; no reset token appears in an API response.
4. Submit `token` and `new_password` to `POST /auth/recovery/reset`; success is
   204. Then log in. Both types of challenge are purpose-bound, single-use,
   cryptographically random, SHA-256 hashed at rest, and expire after 30 minutes
   by default. A new challenge invalidates older challenges of that purpose.
   Confirming an address invalidates outstanding reset challenges. A password
   change/reset invalidates all challenges and cancels pending address changes.

Recovery returns 503 uniformly when not configured. Delivery uses TLS SMTP after
transaction commit. A 202 confirms the request, **not delivery**. Delivery failure
or a worker crash can lose a message; request it again. There is no durable mail
queue in this implementation. See [deployment](deployment.md) before enabling it.
Forgotten passwords for never-enrolled accounts cannot be securely recovered from
username alone; there is no unauthenticated address-registration shortcut.

## Validation

Create, parent update, nested update, and item endpoints share input constraints:

- Required names (`username`, profile `name`, `meal_type`, `workout_name`, item
  `name`/`exercise_name`) are nonblank, maximum 200 characters. Registration now
  requires a profile name; profile PUT is still a full profile replacement.
- Nutrition/macros, sets/reps, weights, all durations are finite and nonnegative.
  Positive item weights require `weight_unit` (see Units).
  Integer fields reject booleans, fractional/string numbers and signed-64-bit overflow.
- Meal `date` is a real `YYYY-MM-DD` date; `time` is an optional local wall time
  `HH:MM` or `HH:MM:SS`, with `""` meaning unknown. Meal dates/times do not infer
  timezone. `meal_type` is a nonblank name rather than a fixed enum.
- Profile age is 0–130, height 0–300 cm, weight 0–700 kg; zero means unspecified,
  preserving prior optional numeric defaults. Gender and activity retain the
  existing enums. Goals/sports remain optional string lists.
  `weekly_workout_target` is an integer 1–14 workouts per week, or `null` for no
  target (the default, and the value for existing profiles); as part of the full
  profile replacement, omitting it removes the target.
- Passwords use the existing policy (seven letters/spaces, uppercase, a number,
  and punctuation/symbol), bcrypt cost 10, and at most **72 UTF-8 bytes**. Oversize
  passwords return 400 everywhere, including login and confirmation. They are
  never silently truncated. Historical TEXT/BLOB bcrypt hashes remain readable.

Existing invalid historical values are not rewritten by migration. Response
schemas do not apply new input bounds to old rows; malformed stored data that
cannot be represented returns the existing JSON 500 error.

## Nested writes and meal totals

Meal POST now persists supplied nested `items` and returns their generated IDs
and calculated `total_calories`. Supplied totals are ignored; totals always come
from persisted children. Workout POST continues to persist nested items.
New parents reject nonzero child IDs/parent IDs.

Meal and workout PUT now use the same nested-list semantics:

| `items` value | Behavior |
|---|---|
| Omitted or null | Preserve existing children |
| `[]` | Delete all children |
| Nonempty list | Replace the collection; update listed existing IDs, insert entries with missing/zero ID, delete omitted children |

Existing IDs must belong to the owned parent; mismatched parent IDs or foreign
children return 404. Duplicate existing child IDs return 400. Each item is a full
replacement; omitted numeric values default to zero. Nested lists are limited to
500 supplied entries. Parent, child and record changes roll back together on any
failure. Workout PUT returns persisted children, including generated IDs; it no
longer echoes unpersisted input. Meal PUT retains its 204 response. Empty `items`
are still omitted from meal/workout responses. Dedicated child PUT routes retain
their path-ID semantics (body IDs are ignored).

Workout record maintenance uses normalized exercise names, the highest positive
weight in kilograms, and lowest item ID to break ties. Rename, unit changes,
replacement, and deletion recompute affected records, including fallback candidates
in other workouts. Zero-weight items remain stored but do not rank.

## Units

- Workout items have `weight_unit`: `"kg"`, `"lb"`, or `null` (unknown). It is
  required whenever `weight` is positive, on every create, child update and nested
  replacement; otherwise 400 `weight_unit (kg or lb) is required when weight is
  positive`. Weightless items may omit it. Items logged before revision 0003 keep
  `null`; the API never guesses. Users fix old items by editing them with a unit.
- Personal records, `GET /social/leaderboard` and `GET /social/muscle-ranks` compare
  kilograms (1 lb = 0.45359237 kg). `max_weight` is always **kilograms**. Items with
  an unknown unit never rank, so rankings start empty after the upgrade and fill as
  users log or edit items with units.
- Workouts have `duration_minutes`, the overall minutes (nonnegative number, `null`
  unknown). POST omission means unknown; on PUT, omission preserves the stored
  value and `null` clears it. The legacy integer `duration` has no defined unit and
  is **deprecated**: it is still returned and accepted, but new clients should write
  only `duration_minutes`. On PUT an omitted `duration` now preserves the stored
  value (it previously reset to 0), so clients that stop sending it keep old data.
- Profiles have `unit_preference`: `"metric"` (default) or `"imperial"`. It is a
  display preference only; profile height/weight remain whole cm/kg. Profiles
  created before revision 0003 read as `"metric"`. Profile PUT remains a full
  replacement, so omitting it restores `"metric"`.

## Meals by date and daily summary

`GET /nutrition/meals?date=YYYY-MM-DD` returns only the caller's meals whose `date`
equals that local calendar date, with the same `limit`/`offset` paging and ID order.
Without `date` it returns every meal, as before.

`GET /nutrition/summary?date=YYYY-MM-DD` (date required) returns that day's totals
across all of the caller's meal items and the caller's macro targets:

```json
{"date":"2026-09-25","calories":600,"protein":26,"carbs":72,"fat":15,
 "targets":{"user_id":1,"calories_target":2000,"protein_target":0,
            "carbs_target":250,"fat_target":70}}
```

Days without meals return zeros. `targets` is `null` when none are configured
(where `GET /nutrition/macros` returns 404). An invalid or missing date returns 400
`Invalid date`. Dates are compared as stored; the server never applies a timezone,
so clients send the user's local date. Revision `0004_meal_dates` indexes
`meals(user_id, date, id)` for both queries.

## Favorite meals

Favorites are reusable meal templates: a `name`, a default `meal_type`, and items
with the same fields and validation as meal items (up to 500). They have no date or
time. All routes are owner-scoped; another user's favorite returns 404.

| Endpoint | Result |
|---|---|
| GET `/nutrition/favorites` | 200 page (`limit`/`offset`, ID order) |
| POST `/nutrition/favorites` | 201 favorite with generated item IDs |
| GET `/nutrition/favorites/{id}` | 200 favorite |
| PUT `/nutrition/favorites/{id}` | 200 favorite; replaces `name`/`meal_type`; `items` omitted or null keeps them, a list (including `[]`) replaces them all with new IDs |
| DELETE `/nutrition/favorites/{id}` | 204; items are deleted with it |
| POST `/nutrition/favorites/{id}/log` | 201 `MealResponse` for a new meal |

A favorite response always includes `items` (possibly `[]`) and a `total_calories`
calculated from them. The log body takes `date` (required, `YYYY-MM-DD`), optional
`time` (`HH:MM[:SS]`, default unknown) and optional `meal_type` (default: the
favorite's). Logging copies the items into an ordinary meal; later edits or
deletion of the favorite never change meals already logged. Favorites cascade on
account deletion.

## Friend discovery

`GET /social/users/search?q=PREFIX` finds users whose username starts with `q` (3–200
characters; otherwise 400 `Invalid q`). ASCII letters match case-insensitively;
other characters match exactly, and `%`/`_` are literal. It returns at most 20
results ordered by username, each exactly `{"id", "username", "name"}` (`name` is the
profile name, or `null` without a profile). No other profile field is exposed. The
caller and anyone with a block in either direction are excluded; pending and
accepted friends remain visible. There is no pagination. Requests share a per-IP
bucket (`SEARCH_RATE_LIMIT`, default 60 per window) and return 429 with
`Retry-After` when exhausted; attempts count before authentication. Send a friend
request with the returned `id` through `POST /social/friendships`.

## Health data (Apple Health and Health Connect)

The mobile app imports data from Apple Health (iOS, provider `apple_health`) or
Health Connect (Android, provider `health_connect`). Neither platform has a server
API: the app asks the OS for read access, reads on the device, and uploads windows
of data here. The server never contacts Apple or Google. Imported data lives in its
own tables and never appears in workouts, personal records, leaderboards, streaks,
`profiles.weight` or macro targets. This revision adds no endpoints that read the
imported rows back.

| Endpoint | Result |
|---|---|
| GET `/health/connections` | 200 list with both providers, always in the order `apple_health`, `health_connect` |
| PUT `/health/connections/{provider}` | 200 connection; body `{"data_types": [...]}` (1–6 unique types the user granted). Connecting again updates the types and keeps `connected_at` |
| DELETE `/health/connections/{provider}` | 204; disconnects only. Syncing stops, imported data is kept, `last_synced_at` resets so a reconnect backfills again |
| DELETE `/health/connections/{provider}/data` | 204; permanently deletes everything imported from that provider, connected or not, and resets `last_synced_at` |
| POST `/health/connections/{provider}/sync` | 200 connection after storing one window; 409 when not connected |

An unknown provider returns 400 `Invalid provider`. Data types are `steps`,
`active_energy`, `heart_rate`, `resting_heart_rate`, `workouts` and `weight`. A
connection reports `connected`, `data_types` (`[]` when disconnected),
`connected_at`, `last_synced_at`, and row counts `synced_days`, `synced_workouts`
and `synced_weights` (counts stay after a disconnect).

A sync body covers one window:

```json
{"since":"2026-09-01T05:00:00Z","until":"2026-09-08T05:00:00Z",
 "data_types":["steps","active_energy","heart_rate","resting_heart_rate","workouts","weight"],
 "daily":[{"date":"2026-09-01","steps":8000,"active_energy_kcal":420.5,
           "resting_heart_rate_bpm":58,"heart_rate_min_bpm":52,
           "heart_rate_avg_bpm":71.5,"heart_rate_max_bpm":160}],
 "workouts":[{"external_id":"6F1C…","activity_type":"running",
              "source_type":"HKWorkoutActivityTypeRunning",
              "start_at":"2026-09-02T12:00:00Z","end_at":"2026-09-02T12:30:00Z",
              "energy_kcal":300,"avg_heart_rate_bpm":140,"max_heart_rate_bpm":171,
              "source_name":"Apple Watch"}],
 "weights":[{"external_id":"9A2B…","measured_at":"2026-09-02T06:00:00Z","weight_kg":80.0}]}
```

- `since` (inclusive) and `until` (exclusive) are timezone-aware timestamps, at most
  31 days apart, with `until` no more than a day after server time. Every
  `data_types` entry must be one the connection granted.
- The server only touches the listed types. Daily rows (one per device-local
  `YYYY-MM-DD`, at most 31, within a day of the window) are upserted, writing only
  the columns of listed types: `steps` → `steps`, `active_energy` →
  `active_energy_kcal`, `resting_heart_rate` → `resting_heart_rate_bpm`,
  `heart_rate` → the min/avg/max columns. Clients send every day in the window,
  with zero steps/energy where there was none, so a later sync corrects a day.
  Heart rates are `null` when there was no reading.
- With `workouts` listed, the provider's sessions whose `start_at` is in the window
  (and any re-sent `external_id` stored elsewhere) are **replaced** by the ones
  sent, so edits and deletions at the source propagate. `weight` works the same way
  on `measured_at`. Workout heart rates are stored only when `heart_rate` is listed.
- Activity types are `running`, `walking`, `cycling`, `swimming`,
  `strength_training`, `hiit`, `yoga` or `other`; `source_type` keeps the
  platform's own type. Weights are kilograms.
- Bounds: steps 0–200,000 per day, energy 0–20,000 kcal, heart rate 20–250 bpm
  (min ≤ avg ≤ max), weight 20–400 kg, sessions longer than zero and at most 24
  hours, at most 500 workouts and 500 weights, unique `external_id`s per request.
- The whole window is one transaction: any invalid row rejects the request and
  nothing is written. Resending a window is idempotent.
- `last_synced_at` becomes the window's `until`, capped at server time. Clients
  start the next window two days before it.

Sync requests share a per-IP bucket (`HEALTH_SYNC_RATE_LIMIT`, default 30 per
window; 429 with `Retry-After`). Responses carry `Cache-Control: no-store`, and
request bodies are never logged. The public probes `/health/live` and
`/health/ready` are unrelated and stay unauthenticated.

How the mobile app pairs, reads and syncs (and how to test it on an emulator) is
described in the frontend's
[`docs/health-integration.md`](../../gopher-fit-front/docs/health-integration.md).

## Workout history and pagination

`occurred_at` on workout POST/PUT is an ISO 8601 timestamp with `T` and an explicit
UTC offset, e.g. `2026-09-25T08:30:00-05:00`. It is stored and returned in UTC.
Naive timestamps, dates alone, and numeric epoch inputs return 400. On POST,
omitted/null means unknown. On PUT, omission preserves the timestamp and null
clears it. Migrated workouts have null times; IDs are never used to infer dates.

`GET /workouts/?start=...&end=...` accepts timezone-aware timestamps. Start is
inclusive, end exclusive; start must precede end. Supplying either bound excludes
unknown times. URL-encode `+` in offsets. Results order by `occurred_at DESC, id
DESC`, with unknown times last. This intentionally changes prior ID ordering.

Meals, workouts, all friendship collections, leaderboard and muscle-rank lists
accept `limit` (default 50, 1–100) and `offset` (default 0, 0–1,000,000). Responses
remain JSON arrays; no total envelope is added. Continue until a page is shorter
than the limit (an exact multiple requires one empty final page). Offset paging
is deterministic for unchanged data; concurrent inserts/deletes can shift pages.

Meals keep ID ascending order. Friendships order by `(user1_id, user2_id)`;
leaderboards by weight descending/user ID ascending; muscle ranks by exercise key.
Window functions calculate ranks/percentiles over the **whole exercise population
before pagination**. Weights 300, 200, 200, 100 retain ranks 1, 2, 2, 3 and percentiles
100, 75, 75, 25 on every page. Ownership filters and friendship transition rules
remain unchanged. Meal/workout lists fetch children once per page, not per parent.
