# API and frontend contract

OpenAPI is generated at `/swagger/doc.json`; Swagger UI remains at
`/swagger/index.html`. The exported [OpenAPI snapshot](openapi.json) is verified
by `make check`. All original method/path pairs remain. Responses use
`{"error":"message"}` for errors, including HTTP 400 validation, 401 auth, 404
ownership mismatches, 409 conflicts, 429 throttles, and 503 unavailable recovery.
Unknown fields remain ignored; explicit null scalars are rejected unless documented
as nullable. No 422 `detail` envelope is used. Request IDs appear in `X-Request-ID`.

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
and items, macro goals, workouts and items, personal records, all friendships
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
  Integer fields reject booleans, fractional/string numbers and signed-64-bit overflow.
- Meal `date` is a real `YYYY-MM-DD` date; `time` is an optional local wall time
  `HH:MM` or `HH:MM:SS`, with `""` meaning unknown. Meal dates/times do not infer
  timezone. `meal_type` is a nonblank name rather than a fixed enum.
- Profile age is 0–130, height 0–300 cm, weight 0–700 kg; zero means unspecified,
  preserving prior optional numeric defaults. Gender and activity retain the
  existing enums. Goals/sports remain optional string lists.
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
weight, and lowest item ID to break ties. Rename, replacement, and deletion
recompute affected records, including fallback candidates in other workouts.
Zero-weight items remain stored but do not rank. No unit conversion is applied.

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
