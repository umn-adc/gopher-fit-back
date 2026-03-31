package workouts

import (
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
		rows.Scan(&workout.ID, &workout.UserID, &workout.WorkoutName, &workout.Duration)
		workout.Items = []WorkoutItem{}
		workouts = append(workouts, workout)
	}
	rows.Close()

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
			itemRows.Scan(&item.ID, &item.WorkoutID, &item.ExerciseName, &item.Sets, &item.Reps, &item.Weight, &item.DurationMinutes)
			workouts[i].Items = append(workouts[i].Items, item)
		}
		itemRows.Close()
	}

	api.WriteSuccess(w, http.StatusOK, workouts)
}

// @Summary Create a workout
// @Tags workouts
// @Security BearerAuth
// @Param request body Workout true "Workout data"
// @Success 201 {object} Workout
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

	tx, err := h.DB.Begin()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error beginning transaction", err)
		return
	}
	result, err := tx.Exec(`
		INSERT INTO workouts (user_id, workout_name, duration) VALUES (?, ?, ?)
	`, workout.UserID, workout.WorkoutName, workout.Duration)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error creating workout", err)
		tx.Rollback()
		return
	}

	workoutID, _ := result.LastInsertId()
	workout.ID = int(workoutID)

	for i := range workout.Items {
		workout.Items[i].WorkoutID = workout.ID
		_, err := tx.Exec(`
		INSERT INTO workout_item (workout_id, exercise_name, sets, reps, weight, duration_minutes) VALUES (?, ?, ?, ?, ?, ?)
		`, workout.ID, workout.Items[i].ExerciseName, workout.Items[i].Sets, workout.Items[i].Reps, workout.Items[i].Weight, workout.Items[i].DurationMinutes)
		if err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Error creating workout item", err)
			tx.Rollback()
			return
		}
	}
	tx.Commit()

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
		api.WriteError(w, http.StatusNotFound, "Workout not found", err)
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
		rows.Scan(&item.ID, &item.WorkoutID, &item.ExerciseName, &item.Sets, &item.Reps, &item.Weight, &item.DurationMinutes)
		workout.Items = append(workout.Items, item)
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
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Success 204 "No Content"
// @Router /workouts/{id} [delete]
func (h *Handler) deleteWorkout(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	id, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	result, err := h.DB.Exec(`DELETE FROM workouts WHERE id = ? AND user_id = ?`, id, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error deleting workout", err)
		return
	}

	if !api.CheckAffected(w, result, "Workout not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
