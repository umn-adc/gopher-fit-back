package workouts

import (
	"net/http"
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
}
