package workouts

import (
	"net/http"

	"gopherfit/internal/api"
)

// @Summary Add exercise to workout
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param request body WorkoutItem true "Exercise data"
// @Success 201 {object} WorkoutItem
// @Router /workouts/{id}/items [post]
func (h *Handler) addWorkoutItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	workoutID, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	var item WorkoutItem
	if !api.DecodeJSON(w, r, &item) {
		return
	}

	res, err := h.DB.Exec(`
		INSERT INTO workout_item (workout_id, exercise_name, sets, reps, weight, duration_minutes)
		SELECT ?, ?, ?, ?, ?, ? WHERE EXISTS (
			SELECT 1 FROM workouts WHERE id = ? AND user_id = ?
		)`, workoutID, item.ExerciseName, item.Sets, item.Reps, item.Weight, item.DurationMinutes, workoutID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert workout item", err)
		return
	}

	if !api.CheckAffected(w, res, "Workout not found") {
		return
	}

	id, _ := res.LastInsertId()
	item.ID = int(id)
	item.WorkoutID = workoutID
	api.WriteSuccess(w, http.StatusCreated, item)
}

// @Summary Update exercise
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param itemId path int true "Item ID"
// @Param request body WorkoutItem true "Exercise data"
// @Success 200 {object} WorkoutItem
// @Router /workouts/{id}/items/{itemId} [put]
func (h *Handler) updateWorkoutItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	itemID, ok := api.PathInt(w, r, "itemId")
	if !ok {
		return
	}

	var item WorkoutItem
	if !api.DecodeJSON(w, r, &item) {
		return
	}

	result, err := h.DB.Exec(`
		UPDATE workout_item
		SET exercise_name = ?,
			sets = ?,
			reps = ?,
			weight = ?,
			duration_minutes = ?
		WHERE id = ? AND workout_id IN (SELECT id FROM workouts WHERE user_id = ?)`,
		item.ExerciseName, item.Sets, item.Reps, item.Weight, item.DurationMinutes, itemID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error updating workout item", err)
		return
	}

	if !api.CheckAffected(w, result, "Workout item not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// @Summary Delete exercise
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param itemId path int true "Item ID"
// @Success 204 "No Content"
// @Router /workouts/{id}/items/{itemId} [delete]
func (h *Handler) deleteWorkoutItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	workoutID, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	itemID, ok := api.PathInt(w, r, "itemId")
	if !ok {
		return
	}

	res, err := h.DB.Exec(`
		DELETE FROM workout_item WHERE id = ? AND workout_id IN (SELECT id FROM workouts WHERE id = ? AND user_id = ?)`,
		itemID, workoutID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete workout item", err)
		return
	}

	if !api.CheckAffected(w, res, "Workout item not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
