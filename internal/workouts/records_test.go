package workouts

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"testing"

	"gopherfit/internal/testutil"
)

func TestPersonalRecordsTrackWorkoutLifecycle(t *testing.T) {
	conn, client := recordWorkoutFixture(t)
	other := createRecordWorkout(t, client, 2, []WorkoutItem{{ExerciseName: "Bench Press", Weight: 500}})
	w1 := createRecordWorkout(t, client, 1, []WorkoutItem{
		{ExerciseName: " Bench  Press ", Weight: 100},
		{ExerciseName: "bench\tpress", Weight: 120},
		{ExerciseName: "Squat", Weight: 200},
		{ExerciseName: "Run", Weight: 0, DurationMinutes: 30},
	})
	assertPersonalRecord(t, conn, 1, "bench press", 120, w1.Items[1].ID)
	assertPersonalRecord(t, conn, 1, "squat", 200, w1.Items[2].ID)
	assertNoPersonalRecord(t, conn, 1, "run")
	w2 := createRecordWorkout(t, client, 1, []WorkoutItem{{ExerciseName: "BENCH PRESS", Weight: 120}})
	assertPersonalRecord(t, conn, 1, "bench press", 120, w1.Items[1].ID)

	added := addRecordItem(t, client, 1, w2.ID, "  Bench\u00a0Press ", 150)
	assertPersonalRecord(t, conn, 1, "bench press", 150, added.ID)
	addRecordItem(t, client, 1, w2.ID, "bench press", 110)
	assertPersonalRecord(t, conn, 1, "bench press", 150, added.ID)
	updateRecordItem(t, client, w2.ID, added.ID, "Bench Press", 90)
	assertPersonalRecord(t, conn, 1, "bench press", 120, w1.Items[1].ID)

	updateRecordItem(t, client, w1.ID, w1.Items[1].ID, "Deadlift", 180)
	assertPersonalRecord(t, conn, 1, "bench press", 120, w2.Items[0].ID)
	assertPersonalRecord(t, conn, 1, "deadlift", 180, w1.Items[1].ID)
	updateRecordItem(t, client, w2.ID, w2.Items[0].ID, " bench  press ", 125.5)
	assertPersonalRecord(t, conn, 1, "bench press", 125.5, w2.Items[0].ID)
	// Moving a maximum into an existing exercise updates both groups.
	updateRecordItem(t, client, w1.ID, w1.Items[1].ID, "Bench Press", 200)
	assertPersonalRecord(t, conn, 1, "bench press", 200, w1.Items[1].ID)
	assertNoPersonalRecord(t, conn, 1, "deadlift")
	res := client.Request(t, 1, "DELETE", itemPath(w1.ID, w1.Items[1].ID), "")
	testutil.AssertStatus(t, res, 204)
	assertPersonalRecord(t, conn, 1, "bench press", 125.5, w2.Items[0].ID)

	res = client.Request(t, 1, "DELETE", fmt.Sprintf("/workouts/%d", w2.ID), "")
	testutil.AssertStatus(t, res, 204)
	assertPersonalRecord(t, conn, 1, "bench press", 100, w1.Items[0].ID)
	assertPersonalRecord(t, conn, 1, "squat", 200, w1.Items[2].ID)
	// Turning the last weighted lift into a bodyweight exercise removes its record.
	updateRecordItem(t, client, w1.ID, w1.Items[0].ID, "Bench Press", 0)
	assertNoPersonalRecord(t, conn, 1, "bench press")
	res = client.Request(t, 1, "DELETE", fmt.Sprintf("/workouts/%d", w1.ID), "")
	testutil.AssertStatus(t, res, 204)
	assertNoPersonalRecord(t, conn, 1, "squat")
	assertPersonalRecord(t, conn, 2, "bench press", 500, other.Items[0].ID)
}

func TestDeleteTiedRecordPromotesRemainingSource(t *testing.T) {
	conn, client := recordWorkoutFixture(t)
	w := createRecordWorkout(t, client, 1, []WorkoutItem{{ExerciseName: "Squat", Weight: 100}, {ExerciseName: "SQUAT", Weight: 100}})
	res := client.Request(t, 1, "DELETE", itemPath(w.ID, w.Items[0].ID), "")
	testutil.AssertStatus(t, res, 204)
	assertPersonalRecord(t, conn, 1, "squat", 100, w.Items[1].ID)
	res = client.Request(t, 1, "DELETE", itemPath(w.ID, w.Items[1].ID), "")
	testutil.AssertStatus(t, res, 204)
	assertNoPersonalRecord(t, conn, 1, "squat")
}

func TestWorkoutAndRecordChangesRollbackTogether(t *testing.T) {
	for _, operation := range []string{"create workout", "add item", "rename item", "delete item", "delete workout"} {
		t.Run(operation, func(t *testing.T) {
			conn, client := recordWorkoutFixture(t)
			w := createRecordWorkout(t, client, 1, []WorkoutItem{{ExerciseName: "Squat", Weight: 200}, {ExerciseName: "Bench Press", Weight: 100}})
			createRecordWorkout(t, client, 1, []WorkoutItem{{ExerciseName: "Squat", Weight: 150}})
			before := workoutRecordSnapshot(t, conn)
			testutil.Exec(t, conn, `CREATE TRIGGER reject_record_write BEFORE INSERT ON personal_records BEGIN SELECT RAISE(ABORT, 'forced record failure'); END`)
			method, path, body := "", "", ""
			switch operation {
			case "create workout":
				method, path, body = "POST", "/workouts/", `{"workout_name":"Rollback","items":[{"exercise_name":"Squat","weight":250}]}`
			case "add item":
				method, path, body = "POST", fmt.Sprintf("/workouts/%d/items", w.ID), `{"exercise_name":"Squat","weight":250}`
			case "rename item":
				method, path, body = "PUT", itemPath(w.ID, w.Items[0].ID), `{"exercise_name":"Deadlift","weight":250}`
			case "delete item":
				method, path = "DELETE", itemPath(w.ID, w.Items[0].ID)
			case "delete workout":
				method, path = "DELETE", fmt.Sprintf("/workouts/%d", w.ID)
			}
			res := client.Request(t, 1, method, path, body)
			testutil.AssertStatus(t, res, 500)
			if strings.Contains(res.Body.String(), "forced record failure") {
				t.Fatal("internal error leaked")
			}
			if after := workoutRecordSnapshot(t, conn); after != before {
				t.Fatalf("failed operation changed data:\nbefore=%s\nafter=%s", before, after)
			}
		})
	}
}

func TestRecordMutationsEnforceOwnershipAndParent(t *testing.T) {
	conn, client := recordWorkoutFixture(t)
	own := createRecordWorkout(t, client, 1, []WorkoutItem{{ExerciseName: "Squat", Weight: 100}})
	otherParent := createRecordWorkout(t, client, 1, nil)
	other := createRecordWorkout(t, client, 2, []WorkoutItem{{ExerciseName: "Squat", Weight: 200}})
	body := `{"exercise_name":"Squat","weight":999,"workout_id":999,"id":999}`
	tests := []struct {
		method, path   string
		userID, status int
	}{
		{"POST", fmt.Sprintf("/workouts/%d/items", other.ID), 1, 404},
		{"PUT", itemPath(other.ID, other.Items[0].ID), 1, 404},
		{"DELETE", itemPath(other.ID, other.Items[0].ID), 1, 404},
		{"DELETE", fmt.Sprintf("/workouts/%d", other.ID), 1, 404},
		{"PUT", itemPath(otherParent.ID, own.Items[0].ID), 1, 404},
		{"DELETE", itemPath(otherParent.ID, own.Items[0].ID), 1, 404},
		{"PUT", itemPath(own.ID, 999), 1, 404},
		{"DELETE", itemPath(own.ID, 999), 1, 404},
		{"POST", "/workouts/999/items", 1, 404},
		{"DELETE", "/workouts/999", 1, 404},
		{"POST", "/workouts/", 0, 401},
		{"POST", fmt.Sprintf("/workouts/%d/items", own.ID), 0, 401},
		{"PUT", itemPath(own.ID, own.Items[0].ID), 0, 401},
		{"DELETE", itemPath(own.ID, own.Items[0].ID), 0, 401},
		{"DELETE", fmt.Sprintf("/workouts/%d", own.ID), 0, 401},
	}
	before := workoutRecordSnapshot(t, conn)
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%s %s user=%d", tt.method, tt.path, tt.userID), func(t *testing.T) {
			res := client.Request(t, tt.userID, tt.method, tt.path, body)
			testutil.AssertStatus(t, res, tt.status)
			if got := workoutRecordSnapshot(t, conn); got != before {
				t.Fatal("rejected mutation changed workouts or records")
			}
		})
	}
}

func TestWorkoutRecordInputValidation(t *testing.T) {
	conn, client := recordWorkoutFixture(t)
	w := createRecordWorkout(t, client, 1, []WorkoutItem{{ExerciseName: "Squat", Weight: 100}})
	before := workoutRecordSnapshot(t, conn)
	for _, body := range []string{
		`{"exercise_name":"","weight":100}`,
		`{"exercise_name":" \t ","weight":100}`,
		`{"exercise_name":"Squat","weight":-1}`,
		`{"exercise_name":"Squat","weight":1e999}`,
		`{"exercise_name":"Squat","weight":"heavy"}`,
	} {
		for _, method := range []string{"POST", "PUT"} {
			path := fmt.Sprintf("/workouts/%d/items", w.ID)
			if method == "PUT" {
				path = itemPath(w.ID, w.Items[0].ID)
			}
			res := client.Request(t, 1, method, path, body)
			testutil.AssertStatus(t, res, 400)
		}
		// A later invalid item must not partially create a workout or records.
		res := client.Request(t, 1, "POST", "/workouts/", `{"items":[{"exercise_name":"Bench","weight":200},`+body+`]}`)
		testutil.AssertStatus(t, res, 400)
	}
	for _, id := range []string{"0", "-1", "not-an-id"} {
		testutil.AssertStatus(t, client.Request(t, 1, "POST", "/workouts/"+id+"/items", `{"exercise_name":"Squat","weight":1}`), 400)
		testutil.AssertStatus(t, client.Request(t, 1, "PUT", "/workouts/"+id+"/items/1", `{"exercise_name":"Squat","weight":1}`), 400)
		testutil.AssertStatus(t, client.Request(t, 1, "DELETE", "/workouts/1/items/"+id, ""), 400)
	}
	if got := workoutRecordSnapshot(t, conn); got != before {
		t.Fatal("invalid input changed workouts or records")
	}
}

func recordWorkoutFixture(t *testing.T) (*sql.DB, *testutil.Client) {
	t.Helper()
	conn := testutil.NewDB(t)
	testutil.Exec(t, conn, `INSERT INTO users (id, username, password) VALUES (1, 'one', X'01'), (2, 'two', X'02')`)
	return conn, testutil.NewClient(t, NewHandler(conn).RegisterRoutes())
}

func createRecordWorkout(t *testing.T, client *testutil.Client, userID int, items []WorkoutItem) Workout {
	t.Helper()
	body, err := json.Marshal(Workout{UserID: 999, WorkoutName: "Records", Duration: 30, Items: items})
	if err != nil {
		t.Fatal(err)
	}
	res := client.Request(t, userID, http.MethodPost, "/workouts/", string(body))
	testutil.AssertStatus(t, res, 201)
	var w Workout
	if err := json.Unmarshal(res.Body.Bytes(), &w); err != nil {
		t.Fatal(err)
	}
	if w.UserID != userID {
		t.Fatalf("workout owner=%d, want=%d", w.UserID, userID)
	}
	return w
}

func addRecordItem(t *testing.T, client *testutil.Client, userID, workoutID int, name string, weight float64) WorkoutItem {
	t.Helper()
	body, err := json.Marshal(WorkoutItem{ID: 999, WorkoutID: 999, ExerciseName: name, Weight: weight})
	if err != nil {
		t.Fatal(err)
	}
	res := client.Request(t, userID, "POST", fmt.Sprintf("/workouts/%d/items", workoutID), string(body))
	testutil.AssertStatus(t, res, 201)
	var item WorkoutItem
	if err := json.Unmarshal(res.Body.Bytes(), &item); err != nil {
		t.Fatal(err)
	}
	if item.WorkoutID != workoutID || item.ID <= 0 || item.ID == 999 {
		t.Fatalf("invalid persisted IDs: %+v", item)
	}
	return item
}

func updateRecordItem(t *testing.T, client *testutil.Client, workoutID, itemID int, name string, weight float64) {
	t.Helper()
	body, err := json.Marshal(WorkoutItem{ExerciseName: name, Weight: weight})
	if err != nil {
		t.Fatal(err)
	}
	res := client.Request(t, 1, "PUT", itemPath(workoutID, itemID), string(body))
	testutil.AssertStatus(t, res, 204)
	if res.Body.Len() != 0 {
		t.Fatalf("update changed the 204 response shape: %s", res.Body.String())
	}
}

func itemPath(workoutID, itemID int) string {
	return fmt.Sprintf("/workouts/%d/items/%d", workoutID, itemID)
}

func assertPersonalRecord(t *testing.T, conn *sql.DB, userID int, key string, wantWeight float64, wantSource int) {
	t.Helper()
	var weight float64
	var source int
	if err := conn.QueryRow(`SELECT max_weight, source_workout_item_id FROM personal_records WHERE user_id = ? AND exercise_key = ?`, userID, key).Scan(&weight, &source); err != nil {
		t.Fatal(err)
	}
	if weight != wantWeight || source != wantSource {
		t.Fatalf("user %d %s record=(%v,%d), want=(%v,%d)", userID, key, weight, source, wantWeight, wantSource)
	}
}

func assertNoPersonalRecord(t *testing.T, conn *sql.DB, userID int, key string) {
	t.Helper()
	var count int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM personal_records WHERE user_id = ? AND exercise_key = ?`, userID, key).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 0 {
		t.Fatalf("unexpected user %d %s record", userID, key)
	}
}

func workoutRecordSnapshot(t *testing.T, conn *sql.DB) string {
	t.Helper()
	var result strings.Builder
	for _, table := range []string{"workouts", "workout_item", "personal_records"} {
		rows, err := conn.Query("SELECT * FROM " + table + " ORDER BY 1, 2")
		if err != nil {
			t.Fatal(err)
		}
		columns, err := rows.Columns()
		if err != nil {
			rows.Close()
			t.Fatal(err)
		}
		for rows.Next() {
			values, pointers := make([]any, len(columns)), make([]any, len(columns))
			for i := range values {
				pointers[i] = &values[i]
			}
			if err := rows.Scan(pointers...); err != nil {
				rows.Close()
				t.Fatal(err)
			}
			fmt.Fprintf(&result, "%s:%v\n", table, values)
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			t.Fatal(err)
		}
		if err := rows.Close(); err != nil {
			t.Fatal(err)
		}
	}
	return result.String()
}
