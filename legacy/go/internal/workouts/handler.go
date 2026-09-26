package workouts

import (
	"database/sql"
	"net/http"
)

type Handler struct {
	DB *sql.DB
}

func NewHandler(db *sql.DB) *Handler {
	return &Handler{DB: db}
}

func (h *Handler) RegisterRoutes() *http.ServeMux {
	r := http.NewServeMux()

	// Workout CRUD
	r.HandleFunc("GET /workouts/", h.getWorkouts)
	r.HandleFunc("POST /workouts/", h.createWorkout)
	r.HandleFunc("GET /workouts/{id}", h.getWorkout)
	r.HandleFunc("PUT /workouts/{id}", h.updateWorkout)
	r.HandleFunc("DELETE /workouts/{id}", h.deleteWorkout)

	// Workout Item CRUD
	r.HandleFunc("POST /workouts/{id}/items", h.addWorkoutItem)
	r.HandleFunc("PUT /workouts/{id}/items/{itemId}", h.updateWorkoutItem)
	r.HandleFunc("DELETE /workouts/{id}/items/{itemId}", h.deleteWorkoutItem)

	return r
}
