package workouts

import (
	"database/sql"
	"net/http"

	"gopherfit/internal/api"
)

// @Summary Get user workouts
// @Tags workouts
// @Security BearerAuth
// @Success 200 {array} Workout
// @Router /workouts/ [get]
func (h *Handler) getWorkouts(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(`SELECT id, user_id, workout_name, duration FROM workouts WHERE user_id = ?`, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error fetching workouts", err)
		return
	}

	workouts := []Workout{}
	for rows.Next() {
		var workout Workout
		if err := rows.Scan(&workout.ID, &workout.UserID, &workout.WorkoutName, &workout.Duration); err != nil {
			rows.Close()
			api.WriteError(w, http.StatusInternalServerError, "Error reading workouts", err)
			return
		}
		workout.Items = []WorkoutItem{}
		workouts = append(workouts, workout)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		api.WriteError(w, http.StatusInternalServerError, "Error while reading workouts", err)
		return
	}
	if err := rows.Close(); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error closing workout query", err)
		return
	}

	for i := range workouts {
		itemRows, err := h.DB.Query(`
			SELECT id, workout_id, exercise_name, sets, reps, weight, duration_minutes
			FROM workout_item WHERE workout_id = ?`, workouts[i].ID)
		if err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Error fetching workout items", err)
			return
		}
		for itemRows.Next() {
			var item WorkoutItem
			if err := itemRows.Scan(&item.ID, &item.WorkoutID, &item.ExerciseName, &item.Sets, &item.Reps, &item.Weight, &item.DurationMinutes); err != nil {
				itemRows.Close()
				api.WriteError(w, http.StatusInternalServerError, "Error reading workout item", err)
				return
			}
			workouts[i].Items = append(workouts[i].Items, item)
		}
		if err := itemRows.Err(); err != nil {
			itemRows.Close()
			api.WriteError(w, http.StatusInternalServerError, "Error while reading workout items", err)
			return
		}
		if err := itemRows.Close(); err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Error closing workout item query", err)
			return
		}
	}

	api.WriteSuccess(w, http.StatusOK, workouts)
}

// @Summary Create a workout
// @Description Creates the workout and its exercise records atomically. Item names must be nonblank and weights finite and nonnegative; only positive weights enter rankings.
// @Tags workouts
// @Security BearerAuth
// @Param request body Workout true "Workout data"
// @Success 201 {object} Workout
// @Failure 400 {object} api.ErrorResponse
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /workouts/ [post]
func (h *Handler) createWorkout(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	var workout Workout
	if !api.DecodeJSON(w, r, &workout) {
		return
	}

	workout.UserID = userID
	names := make([]string, 0, len(workout.Items))
	for _, item := range workout.Items {
		if !validRecordItem(w, item) {
			return
		}
		names = append(names, item.ExerciseName)
	}

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error beginning transaction", err)
		return
	}
	defer api.Rollback(tx)

	result, err := tx.ExecContext(r.Context(), `
		INSERT INTO workouts (user_id, workout_name, duration) VALUES (?, ?, ?)
	`, workout.UserID, workout.WorkoutName, workout.Duration)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error creating workout", err)
		return
	}

	workoutID, err := result.LastInsertId()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error reading workout ID", err)
		return
	}
	workout.ID = int(workoutID)

	for i := range workout.Items {
		workout.Items[i].WorkoutID = workout.ID
		itemResult, err := tx.ExecContext(r.Context(), `
		INSERT INTO workout_item (workout_id, exercise_name, sets, reps, weight, duration_minutes) VALUES (?, ?, ?, ?, ?, ?)
		`, workout.ID, workout.Items[i].ExerciseName, workout.Items[i].Sets, workout.Items[i].Reps, workout.Items[i].Weight, workout.Items[i].DurationMinutes)
		if err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Error creating workout item", err)
			return
		}
		itemID, err := itemResult.LastInsertId()
		if err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Error reading workout item ID", err)
			return
		}
		workout.Items[i].ID = int(itemID)
	}
	if !commitWorkoutRecords(w, r, tx, userID, names...) {
		return
	}

	if workout.Items == nil {
		workout.Items = []WorkoutItem{}
	}
	api.WriteSuccess(w, http.StatusCreated, workout)
}

// @Summary Get workout by ID
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Success 200 {object} Workout
// @Router /workouts/{id} [get]
func (h *Handler) getWorkout(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	id, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	var workout Workout
	err := h.DB.QueryRow(`SELECT id, user_id, workout_name, duration FROM workouts WHERE id = ? AND user_id = ?`, id, userID).
		Scan(&workout.ID, &workout.UserID, &workout.WorkoutName, &workout.Duration)
	if err != nil {
		if err == sql.ErrNoRows {
			api.WriteError(w, http.StatusNotFound, "Workout not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Error fetching workout", err)
		return
	}

	rows, err := h.DB.Query(`SELECT id, workout_id, exercise_name, sets, reps, weight, duration_minutes FROM workout_item WHERE workout_id = ?`, id)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error fetching workout items", err)
		return
	}
	defer rows.Close()

	workout.Items = []WorkoutItem{}
	for rows.Next() {
		var item WorkoutItem
		if err := rows.Scan(&item.ID, &item.WorkoutID, &item.ExerciseName, &item.Sets, &item.Reps, &item.Weight, &item.DurationMinutes); err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Error reading workout item", err)
			return
		}
		workout.Items = append(workout.Items, item)
	}
	if err := rows.Err(); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error while reading workout items", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, workout)
}

// @Summary Update workout
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param request body Workout true "Workout data"
// @Success 200 {object} Workout
// @Router /workouts/{id} [put]
func (h *Handler) updateWorkout(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	id, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	var workout Workout
	if !api.DecodeJSON(w, r, &workout) {
		return
	}

	result, err := h.DB.Exec(`UPDATE workouts SET workout_name = ?, duration = ? WHERE id = ? AND user_id = ?`,
		workout.WorkoutName, workout.Duration, id, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error updating workout", err)
		return
	}

	if !api.CheckAffected(w, result, "Workout not found") {
		return
	}

	workout.ID = id
	workout.UserID = userID
	api.WriteSuccess(w, http.StatusOK, workout)
}

// @Summary Delete workout
// @Description Deletes the workout and its items and recalculates affected personal records in one transaction.
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Success 204 "No Content"
// @Failure 400 {object} api.ErrorResponse
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /workouts/{id} [delete]
func (h *Handler) deleteWorkout(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	id, ok := api.PositivePathInt(w, r, "id")
	if !ok {
		return
	}

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to begin workout deletion", err)
		return
	}
	defer api.Rollback(tx)
	rows, err := tx.QueryContext(r.Context(), `
		SELECT DISTINCT i.exercise_name FROM workout_item i
		JOIN workouts w ON w.id = i.workout_id
		WHERE w.id = ? AND w.user_id = ?`, id, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to read workout exercises", err)
		return
	}
	var names []string
	for rows.Next() {
		var name sql.NullString
		if err := rows.Scan(&name); err != nil {
			rows.Close()
			api.WriteError(w, http.StatusInternalServerError, "Failed to read workout exercise", err)
			return
		}
		names = append(names, name.String)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		api.WriteError(w, http.StatusInternalServerError, "Failed to iterate workout exercises", err)
		return
	}
	if err := rows.Close(); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to close workout exercises", err)
		return
	}

	result, err := tx.ExecContext(r.Context(), `DELETE FROM workouts WHERE id = ? AND user_id = ?`, id, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error deleting workout", err)
		return
	}

	if !api.CheckAffected(w, result, "Workout not found") {
		return
	}
	if !commitWorkoutRecords(w, r, tx, userID, names...) {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
