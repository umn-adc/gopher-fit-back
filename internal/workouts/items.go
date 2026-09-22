package workouts

import (
	"net/http"

	"gopherfit/internal/api"
)

// @Summary Add exercise to workout
// @Description Adds an owned workout item and updates its personal record atomically. Name must be nonblank and weight finite and nonnegative. Zero weights are logged but not ranked.
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param request body WorkoutItem true "Exercise data"
// @Success 201 {object} WorkoutItem
// @Failure 400 {object} api.ErrorResponse
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /workouts/{id}/items [post]
func (h *Handler) addWorkoutItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	workoutID, ok := api.PositivePathInt(w, r, "id")
	if !ok {
		return
	}

	var item WorkoutItem
	if !api.DecodeJSON(w, r, &item) {
		return
	}
	if !validRecordItem(w, item) {
		return
	}

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to begin workout item creation", err)
		return
	}
	defer api.Rollback(tx)
	res, err := tx.ExecContext(r.Context(), `
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

	id, err := res.LastInsertId()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to read workout item ID", err)
		return
	}
	item.ID = int(id)
	item.WorkoutID = workoutID
	if !commitWorkoutRecords(w, r, tx, userID, item.ExerciseName) {
		return
	}
	api.WriteSuccess(w, http.StatusCreated, item)
}

// @Summary Update exercise
// @Description Updates only an item in the caller's specified workout. Renames and weight changes recalculate old and new exercise records atomically. Name must be nonblank and weight finite and nonnegative.
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param itemId path int true "Item ID"
// @Param request body WorkoutItem true "Exercise data"
// @Success 204 "No Content"
// @Failure 400 {object} api.ErrorResponse
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /workouts/{id}/items/{itemId} [put]
func (h *Handler) updateWorkoutItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	workoutID, ok := api.PositivePathInt(w, r, "id")
	if !ok {
		return
	}
	itemID, ok := api.PositivePathInt(w, r, "itemId")
	if !ok {
		return
	}

	var item WorkoutItem
	if !api.DecodeJSON(w, r, &item) {
		return
	}
	if !validRecordItem(w, item) {
		return
	}

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to begin workout item update", err)
		return
	}
	defer api.Rollback(tx)
	oldName, ok := readOwnedExercise(w, r, tx, userID, workoutID, itemID)
	if !ok {
		return
	}
	result, err := tx.ExecContext(r.Context(), `
		UPDATE workout_item
		SET exercise_name = ?,
			sets = ?,
			reps = ?,
			weight = ?,
			duration_minutes = ?
		WHERE id = ? AND workout_id IN (SELECT id FROM workouts WHERE id = ? AND user_id = ?)`,
		item.ExerciseName, item.Sets, item.Reps, item.Weight, item.DurationMinutes, itemID, workoutID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error updating workout item", err)
		return
	}

	if !api.CheckAffected(w, result, "Workout item not found") {
		return
	}
	if !commitWorkoutRecords(w, r, tx, userID, oldName, item.ExerciseName) {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// @Summary Delete exercise
// @Description Deletes an owned workout item and promotes the next-highest lift for the exercise, or removes its record if none remains, in the same transaction.
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param itemId path int true "Item ID"
// @Success 204 "No Content"
// @Failure 400 {object} api.ErrorResponse
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /workouts/{id}/items/{itemId} [delete]
func (h *Handler) deleteWorkoutItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	workoutID, ok := api.PositivePathInt(w, r, "id")
	if !ok {
		return
	}

	itemID, ok := api.PositivePathInt(w, r, "itemId")
	if !ok {
		return
	}

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to begin workout item deletion", err)
		return
	}
	defer api.Rollback(tx)
	oldName, ok := readOwnedExercise(w, r, tx, userID, workoutID, itemID)
	if !ok {
		return
	}
	res, err := tx.ExecContext(r.Context(), `
		DELETE FROM workout_item WHERE id = ? AND workout_id IN (SELECT id FROM workouts WHERE id = ? AND user_id = ?)`,
		itemID, workoutID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete workout item", err)
		return
	}

	if !api.CheckAffected(w, res, "Workout item not found") {
		return
	}
	if !commitWorkoutRecords(w, r, tx, userID, oldName) {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
