package workouts

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"gopherfit/internal/api"
	appdb "gopherfit/internal/db"
)

func TestCreateWorkoutCommitsWorkoutAndItemsTogether(t *testing.T) {
	conn, userID := workoutTestDB(t)
	defer conn.Close()

	handler := NewHandler(conn)
	payload := Workout{
		WorkoutName: "Strength",
		Duration:    45,
		Items: []WorkoutItem{
			{ExerciseName: "Squat", Sets: 3, Reps: 5, Weight: 225},
			{ExerciseName: "Bench Press", Sets: 3, Reps: 5, Weight: 155},
		},
	}
	res := performCreateWorkout(t, handler, userID, payload)
	if res.Code != http.StatusCreated {
		t.Fatalf("status = %d, want %d; body=%s", res.Code, http.StatusCreated, res.Body.String())
	}

	var created Workout
	if err := json.NewDecoder(res.Body).Decode(&created); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if created.ID == 0 || len(created.Items) != 2 || created.Items[0].ID == 0 || created.Items[1].ID == 0 {
		t.Fatalf("created workout does not contain persisted IDs: %+v", created)
	}

	var workouts, items int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM workouts`).Scan(&workouts); err != nil {
		t.Fatalf("count workouts: %v", err)
	}
	if err := conn.QueryRow(`SELECT COUNT(*) FROM workout_item`).Scan(&items); err != nil {
		t.Fatalf("count workout items: %v", err)
	}
	if workouts != 1 || items != 2 {
		t.Fatalf("stored counts = (%d workouts, %d items), want (1, 2)", workouts, items)
	}
}

func TestCreateWorkoutRollsBackWhenAnItemFails(t *testing.T) {
	conn, userID := workoutTestDB(t)
	defer conn.Close()
	if _, err := conn.Exec(`
		CREATE TRIGGER reject_failed_exercise
		BEFORE INSERT ON workout_item
		WHEN NEW.exercise_name = 'fail'
		BEGIN
			SELECT RAISE(ABORT, 'forced item failure');
		END;
	`); err != nil {
		t.Fatalf("create failure trigger: %v", err)
	}

	handler := NewHandler(conn)
	payload := Workout{
		WorkoutName: "Rollback",
		Items: []WorkoutItem{
			{ExerciseName: "Squat", Sets: 1, Reps: 1, Weight: 100},
			{ExerciseName: "fail", Sets: 1, Reps: 1, Weight: 100},
		},
	}
	res := performCreateWorkout(t, handler, userID, payload)
	if res.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, want %d; body=%s", res.Code, http.StatusInternalServerError, res.Body.String())
	}

	var workouts, items int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM workouts`).Scan(&workouts); err != nil {
		t.Fatalf("count workouts: %v", err)
	}
	if err := conn.QueryRow(`SELECT COUNT(*) FROM workout_item`).Scan(&items); err != nil {
		t.Fatalf("count workout items: %v", err)
	}
	if workouts != 0 || items != 0 {
		t.Fatalf("stored counts after rollback = (%d workouts, %d items), want (0, 0)", workouts, items)
	}
}

func workoutTestDB(t *testing.T) (*sql.DB, int) {
	t.Helper()
	conn, err := appdb.Open(filepath.Join(t.TempDir(), "workouts.db"))
	if err != nil {
		t.Fatalf("open test database: %v", err)
	}
	result, err := conn.Exec(`INSERT INTO users (username, password) VALUES (?, ?)`, "workout-user", []byte("hash"))
	if err != nil {
		conn.Close()
		t.Fatalf("insert user: %v", err)
	}
	id, err := result.LastInsertId()
	if err != nil {
		conn.Close()
		t.Fatalf("read user ID: %v", err)
	}
	return conn, int(id)
}

func performCreateWorkout(t *testing.T, handler *Handler, userID int, payload Workout) *httptest.ResponseRecorder {
	t.Helper()
	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal workout: %v", err)
	}
	req := httptest.NewRequest(http.MethodPost, "/workouts/", bytes.NewReader(body))
	req = req.WithContext(context.WithValue(req.Context(), api.CtxUserIDKey, userID))
	res := httptest.NewRecorder()
	handler.RegisterRoutes().ServeHTTP(res, req)
	return res
}
