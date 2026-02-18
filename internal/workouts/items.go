package workouts

import (
	"encoding/json"
	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
	"net/http"
	"strconv"
)

// @Summary Add exercise to workout
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param request body WorkoutItem true "Exercise data"
// @Success 201 {object} WorkoutItem
// @Router /workouts/{id}/items [post]
func (h *Handler) addWorkoutItem(w http.ResponseWriter, r *http.Request) {

	var item WorkoutItem
	if err := json.NewDecoder(r.Body).Decode(&item); err != nil {
		api.WriteError(w, http.StatusBadRequest, "invalid JSON", err)
		return
	}

	query := `
		INSERT INTO workout_item (workout_id, exercise_name, sets, reps, weight, duration)
		VALUES (?, ?, ?, ?, ?, ?);
	`

	_, err := h.DB.Exec(query,
		item.WorkoutID,
		item.ExerciseName,
		item.Sets,
		item.Reps,
		item.Weight,
		item.DurationMinutes,
	)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert workout item", err)
		return
	}

	api.WriteSuccess(w, http.StatusCreated, map[string]string{"message": "Workout item added successfully"})

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
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	id, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid workout-item ID", err)
		return
	}

	var item WorkoutItem
	if err := json.NewDecoder(r.Body).Decode(&item); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	result, err := h.DB.Exec(`
		UPDATE workout_item 
		SET excercise_name = ?,
			sets = ?,
			reps = ?,
			weight = ?,
			duration_minutes = ?
		WHERE id = ? AND workout_id = ?`,
		item.ExerciseName, item.Sets, item.Reps, item.Weight, item.DurationMinutes, id, item.WorkoutID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error updating workout", err)
		return
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		api.WriteError(w, http.StatusNotFound, "Workout-item not found", nil)
		return
	}
}

// @Summary Delete exercise
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param itemId path int true "Item ID"
// @Success 204 "No Content"
// @Router /workouts/{id}/items/{itemId} [delete]
func (h *Handler) deleteWorkoutItem(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}
