package workouts

import (
	"database/sql"
	"math"
	"net/http"

	"gopherfit/internal/api"
	"gopherfit/internal/records"
)

func validRecordItem(w http.ResponseWriter, item WorkoutItem) bool {
	if records.ExerciseKey(item.ExerciseName) == "" || item.Weight < 0 || math.IsNaN(item.Weight) || math.IsInf(item.Weight, 0) {
		api.WriteError(w, http.StatusBadRequest, "Exercise name is required and weight must be finite and nonnegative", nil)
		return false
	}
	return true
}

func commitWorkoutRecords(w http.ResponseWriter, r *http.Request, tx *sql.Tx, userID int, names ...string) bool {
	if err := records.RefreshExercises(r.Context(), tx, userID, names...); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to update personal records", err)
		return false
	}
	if err := tx.Commit(); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to commit workout changes", err)
		return false
	}
	return true
}

// readOwnedExercise captures the old name before rename or deletion, and ties
// the item to both the path's workout ID and the authenticated owner.
func readOwnedExercise(w http.ResponseWriter, r *http.Request, tx *sql.Tx, userID, workoutID, itemID int) (string, bool) {
	var name sql.NullString
	err := tx.QueryRowContext(r.Context(), `
		SELECT i.exercise_name FROM workout_item i
		JOIN workouts w ON w.id = i.workout_id
		WHERE i.id = ? AND w.id = ? AND w.user_id = ?`, itemID, workoutID, userID).Scan(&name)
	if err == sql.ErrNoRows {
		api.WriteError(w, http.StatusNotFound, "Workout item not found", nil)
		return "", false
	}
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to read workout item", err)
		return "", false
	}
	return name.String, true
}
