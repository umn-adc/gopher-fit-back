package workouts

import (
	"net/http"

	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
)

// @Summary Add exercise to workout
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param request body WorkoutItem true "Exercise data"
// @Success 201 {object} WorkoutItem
// @Router /workouts/{id}/items [post]
func (h *Handler) addWorkoutItem(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
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
	// TODO: Implement
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
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	workoutID := r.PathValue("id")
	if workoutID == "" {
		api.WriteError(w, http.StatusBadRequest, "invalid id", nil)
		return
	}

	itemID := r.PathValue("itemId")
	if itemID == "" {
		api.WriteError(w, http.StatusBadRequest, "invalid id", nil)
		return
	}

	query := `DELETE FROM workout_item where id = ? AND workout_id in (SELECT id FROM workouts WHERE id = ? AND user_id = ?)`

	res, err := h.DB.Exec(query, itemID, workoutID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete workout item", err)
		return
	}

	rowsAffected, err := res.RowsAffected()
	if err != nil || rowsAffected == 0 {
		api.WriteError(w, http.StatusNotFound, "workout item not found", err)
		return

	}

	w.WriteHeader(http.StatusNoContent)

}
