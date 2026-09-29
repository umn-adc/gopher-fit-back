# Remote branch triage

Checked 2026-09-29 against `ben/changes` (the Python backend). These are the
remote branches with commits that aren't in `ben/changes`. All of them target the
archived Go server (now in `legacy/go/`), so nothing in them can be merged
directly. Remote branches were not modified or deleted.

| Branch | Author | Last commit | Verdict |
|---|---|---|---|
| `favorite-meals` | Luke Golobitsh | 2026-04-07 | Ported in milestone 2f (D7) |
| `macrogoals` | sakif | 2026-04-07 | Superseded |
| `streaks` | Jia Lauber | 2026-03-31 | Superseded (D8) |
| `websockets` | Luke Golobitsh | 2026-04-07 | Out of scope (D9) |
| `leaderboard` | Abdullahi | 2025-11-03 | Superseded |
| `friend` | Xiajing Pei | 2025-11-18 | Superseded |
| `kieran/meals` | Kieran Finger | 2025-11-04 | Superseded |
| `Reema` | Reema | 2025-11-18 | Out of scope (practice exercise) |

## Details

### `favorite-meals` (1 commit, "Started")

Adds `favorite_meals` (a copy of the `meals` columns, including `date`, `time`
and `total_calories`) and `favorite_meal_items` tables, handlers to list, create,
get, update and delete favorites, and a handler that copies an existing meal into
favorites. It's unfinished: no routes are registered, the favorite insert passes
four values for five placeholders, delete filters on a nonexistent `meal_id`
column, the list scans six of seven columns, and creating a favorite ignores its
items.

**Verdict: ported in milestone 2f (D7).** The idea (reusable meal templates with
items, then logging one as a real meal) is redesigned in the Python layering
under `/nutrition/favorites` with cascading keys. A template has no date or time;
those are chosen when it is logged.

### `macrogoals` (1 commit, "Macros")

Implements `GET /nutrition/macros`, `PUT /nutrition/macros` as an upsert, and a
new insert-only `POST /nutrition/macros` (201; a second POST would fail on the
unique user key with a 500).

**Verdict: superseded.** The Python API already has authenticated
`GET`/`PUT /nutrition/macros`, with the PUT as a validated upsert of all four
targets. POST adds no capability beyond PUT, so nothing is missing.

### `streaks` (1 commit, "added streaks functionality")

A standalone `package main` prototype in `internal/workouts/streaks.go` with an
in-memory `UserStreak`, UTC day boundaries, `CheckIn`/`GetStreak`, and a demo
`main()`. It has no persistence or route, and a `main` package inside the
`workouts` package directory would not build.

**Verdict: superseded (D8).** Streaks are derived client-side from distinct
local workout dates (`gopher-fit-front/lib/stats.ts`), which handles the user's
own timezone rather than UTC days.

### `websockets` (4 commits, including a merge of `dev`)

Adds `gorilla/websocket`, a hub/client skeleton at the repository root,
`chats`/`chat_member`/`messages` tables (the DDL has trailing-comma syntax
errors), and a messaging handler with no registered routes. The Go code
references undefined fields and doesn't compile.

**Verdict: out of scope (D9).** Messaging isn't part of this work.

### `leaderboard` (1 commit)

Adds a `social_stats` table with follower/following/post counts, a stored rank,
and `streak_days`.

**Verdict: superseded.** Rankings are computed from `personal_records` with
window functions (`GET /social/leaderboard`, `GET /social/muscle-ranks`), so a
stored rank would go stale. Followers and posts have no feature behind them,
and streaks are client-side.

### `friend` (1 commit, "create friend table")

Adds a `friends(user_id, friend_id)` table (with a stray `);` that breaks the DDL).

**Verdict: superseded** by the `friendships` table with status and acting user,
and the `/social/friendships` routes (requests, accept, block, unblock).

### `kieran/meals` (2 commits)

Adds `carbs_target`/`fat_target` to `macro_goals`, embeds a `Macros` struct in
`MealItem`, and a stub `GET /nutrition/goals` that reads meals by a `user_id`
query parameter without authentication (marked TODO).

**Verdict: superseded.** `macro_goals` already has all four targets, and
`GET /nutrition/macros` reads them for the authenticated user.

### `Reema` (1 commit, "task1")

Adds a practice endpoint, `GET /practice/reema?name=`.

**Verdict: out of scope.** It's an onboarding practice exercise, not app
functionality.

## Branches fully contained in `ben/changes`

These have no commits outside `ben/changes`: `Friendships`, `MVPfinaltouches`,
`Mamta`, `Refactor-Spring`, `bryan-updatemealitem`, `create-user-table`,
`deleteMeal`, `deleteMealItem`, `deleteWorkoutItem`, `dev`,
`justin/POST-workout`, `justin/verify-jwt`, `kiearn/mealTasks`, `master`,
`userPassChange`, `workout-item`, `zayaan_endpointpractice`.
