package workouts

import (
	"net/http"
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
	// TODO: Implement
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}
	if err := json.NewDecoder(r.Body).Decode(&workout); err != nil {
		api.WriteError(w, http.StatusBadRequest, "invalid JSON", err)
		return
	}
	var workout Workout
	query :=`
		INSERT INTO workouts (UserID, WorkoutName, Duration,)
		VALUES (?, ?, ?);
	`
		_, err := h.DB.Exec(query,
		UserID,
		workout.WorkoutName,
		workout.Duration,
	)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to create workout", err)
		return
	}

	workoutNames, err := h.getWorkoutsNames(userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch workouts", err)
		return
	}

	api.WriteSuccess(w, http.StatusCreated, workoutNames)
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
