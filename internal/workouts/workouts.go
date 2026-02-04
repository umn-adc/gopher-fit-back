package workouts

import (
	"encoding/json"
	"net/http"

	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
)

// @Summary Get user workouts
// @Tags workouts
// @Security BearerAuth
// @Success 200 {array} Workout
// @Router /workouts/ [get]
func (h *Handler) getWorkouts(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}

// @Summary Create a workout
// @Tags workouts
// @Security BearerAuth
// @Param request body Workout true "Workout data"
// @Success 201 {object} Workout
// @Router /workouts/ [post]
func (h *Handler) createWorkout(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	var workout Workout
	if err := json.NewDecoder(r.Body).Decode(&workout); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	if userID != workout.UserID {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	// Begin transaction
	tx, err := h.DB.Begin()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error beginning transaction", err)
		tx.Rollback()
		return
	}
	_, err = tx.Exec(`
		INSERT INTO workouts (id, user_id, workout_name, duration) VALUES (?, ?, ?, ?)
	`, workout.ID, workout.UserID, workout.WorkoutName, workout.Duration)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error creating workout", err)
		tx.Rollback()
		return
	}

	for _, item := range workout.Items {
		_, err := tx.Exec(`
		INSERT into workout_item (id, workout_id, exercise_name, sets, reps, weight, duration_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)
		`, item.ID, item.WorkoutID, item.ExerciseName, item.Sets, item.Reps, item.Weight, item.DurationMinutes)
		if err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Error creating workout item", err)
			tx.Rollback()
			return
		}
	}
	// End transaction
	tx.Commit()

	api.WriteSuccess(w, http.StatusCreated, "Success Creating Workout")
}

// @Summary Get workout by ID
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Success 200 {object} Workout
// @Router /workouts/{id} [get]
func (h *Handler) getWorkout(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}

// @Summary Update workout
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Param request body Workout true "Workout data"
// @Success 200 {object} Workout
// @Router /workouts/{id} [put]
func (h *Handler) updateWorkout(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}

// @Summary Delete workout
// @Tags workouts
// @Security BearerAuth
// @Param id path int true "Workout ID"
// @Success 204 "No Content"
// @Router /workouts/{id} [delete]
func (h *Handler) deleteWorkout(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}
