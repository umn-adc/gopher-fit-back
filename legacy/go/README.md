# Gopher Fit Backend
Welcome to the backend for **Gopher Fit**, a fitness tracking app built with **Go**, and **SQLite**.

## Setup
Make sure you have these downloaded
- [Go 1.22+](https://go.dev/dl/)
- [Git](https://git-scm.com/)

Then clone this repository into your computer's root folder (recommended)
```
https://github.com/umn-adc/gopher-fit-back
```
Then enter the project folder and open it in your IDE
```
cd gopher-fit-back
code .
```

Once you're in, check your dependencies by running
```
go mod tidy
```

To start the Go server, ensure you're in the project root, then run
```
$env:JWT_SECRET = "replace-with-a-long-random-secret"
go run .
```

On macOS or Linux, set the same required variable with
`export JWT_SECRET="replace-with-a-long-random-secret"`. The server refuses to
start without a JWT secret; do not commit real secrets to the repository.

You should now see in the terminal:
```
Listening on port: 3000
```

## API behavior

All routes below require `Authorization: Bearer <token>`. Errors use
`{"error":"message"}`. Swagger UI is available at `/swagger/index.html`.

`PUT /nutrition/meals/{id}/items/{itemId}` updates an item in a meal owned by
the caller. The path supplies both IDs; body IDs are ignored. Supply a nonblank
`name` and nonnegative integer `calories`, `protein`, `carbs`, and `fat` values
(omitted nutrition values default to zero). A successful response includes the
persisted `id` and `meal_id`. Invalid input returns 400; missing items, mismatched
parents, and another user's items all return 404.

`POST /social/friendships` takes `user1_id`, `user2_id`, and `status`. The IDs
must be distinct, positive, refer to existing users, and include the caller.
New relationships can be `pending` or `blocked`. The server sets
`action_user_id` to the caller, ignoring any supplied value. Responses keep the
existing fields and store the smaller ID as `user1_id`. Missing users return
404; an existing pair returns 409.

`PUT /social/friendships/{user2_id}` uses the other user's ID in the path and
requires the same pair of IDs in the body (either order), plus the new status.
The following transitions are supported:

| Current relationship | Who may act | New status |
|---|---|---|
| Pending | Request recipient | Accepted |
| Pending | Either participant | Blocked |
| Accepted | Either participant | Pending or blocked |
| Blocked | User who created the block | Pending |

Same-status changes, invalid statuses, changes to participant IDs, and changes
to an incoming block return 400. Returning to pending makes the caller the new
request sender. `DELETE` on the same path removes a pending or accepted
relationship for either participant; only the blocker may remove a block.
Missing relationships return 404. If the relationship changes between the
authorization check and a mutation, the request returns 409; reload before
retrying. These rules preserve the existing transition behavior.

The friendship collection routes (`/social/friendships`, `/accepted`,
`/outpending`, `/inpending`, `/outblocks`, and `/inblocks`, with the latter five
relative to `/social/friendships`) return only the caller's relationships.
Empty collections return `[]`.

`GET /profile/{id}` lets an authenticated caller resolve a positive user ID to
exactly `{"user_id":1,"username":"gopher"}`. It never returns passwords or
private profile fields. Invalid IDs return 400, absent users 404, and missing
authentication 401. `GET /profile/` continues to return the caller's private
profile. No database migration is required for the meal-item, friendship, or
public-profile changes above.

### Personal records and exercise rankings

`GET /social/muscle-ranks` returns the authenticated caller's personal records,
ordered by normalized exercise name. Each entry includes `user_id`,
`exercise_key`, `exercise_name`, `max_weight`, `source_workout_item_id`, `rank`,
and `percentile`. The source item identifies the caller's own recorded lift;
private workout details are not exposed for other participants.

`GET /social/leaderboard?exercise=Bench%20Press` returns one entry per user who
has a positive-weight record for that exercise, containing `user_id`,
`username`, `max_weight`, `rank`, and `percentile`. This replaces the static
leaderboard: **clients must now provide `exercise` and read `max_weight`
instead of `score`**. Missing or blank exercise names return 400; an exercise
with no participants returns `[]`. Both ranking routes require authentication
and return JSON errors on database failure.

Exercise keys are trimmed, have internal whitespace collapsed (including
Unicode whitespace), and are lowercased. For example, ` Bench   Press ` and
`BENCH PRESS` share the key `bench press`. Display names retain the winning
lift's capitalization with whitespace collapsed. The highest positive weight
per user wins; tied lifts for that user select the lowest workout-item ID as a
stable source. Weight uses the existing application unit; no conversion is
performed. Zero-weight exercises can still be logged, but do not enter rankings.

Ranks use descending dense rank: weights `300, 200, 200, 100` have ranks
`1, 2, 2, 3`. Percentile is `100 * users at or below this weight / participants`
for that exercise, giving `100, 75, 75, 25` in the same example. Ties share rank
and percentile, and leaderboard ties are ordered by user ID. Personal ranks
use the full exercise population before filtering to the caller. These rankings
use recorded weights without verification, composite scores, or friend/group
filtering.

Database migration 3 creates and backfills `personal_records` at startup.
Historical workout items remain unchanged; null/blank names, nonpositive
weights, and nonfinite weights are excluded from records. New workout items
require nonblank names and finite, nonnegative weights. Workout and item
creation, item edits/renames/deletions, and workout deletion recalculate affected
records in the same transaction. Removing a maximum promotes the next-highest
remaining lift, or removes the record when none remains. Failed record updates
roll back the workout mutation. Item updates and deletions require both the
correct parent-workout ID and ownership. Existing successful workout response
formats are preserved, including 204 for item updates.

## Verification and API documentation

Run `go test ./...` and `go vet ./...` after changes. The endpoint tests use
isolated in-memory SQLite databases and the application's JWT middleware.
Regenerate Swagger artifacts after editing endpoint annotations:

```powershell
go run github.com/swaggo/swag/cmd/swag@v1.16.6 init --parseInternal
```

## 📚 Readings
Get a feel for the technologies we’ll be working with!

Before starting any project work, take the Knowledge Quiz below to review key technologies and spot any knowledge gaps: https://forms.gle/32umqmV6hDcfohybA

### 1. REST APIs
Understand how backend services communicate through HTTP requests and JSON.
- [Learn REST APIs (Codecademy)](https://www.codecademy.com/article/what-is-rest) (Read fully)

### 2. Go Basics
Familiarize yourself with Go syntax, types and functions/
- [Learn Go (Official Tour)](https://go.dev/tour) (Read until you are comfortable with basic syntax)

### 3. SQL & SQLite
Learn how relational databases work and how to query data efficiently.
- [What is a relational database?](https://cloud.google.com/learn/what-is-a-relational-database) (Read first 3 sections)
- [Learn SQL / SQLite](https://www.sqlitetutorial.net/) (Read "what is SQLite?", Section 1-3, and Section 9)
- Optional: Download and learn DB Browser to view the project's SQLite database easily https://sqlitebrowser.org/

## Example Route
All app endpoints are in the internal/ folder.
In gopher-fit-back/internal/macros/post.go there is an example route which handles POST /api/macros
