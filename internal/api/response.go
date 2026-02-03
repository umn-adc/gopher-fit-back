package api

import (
	"encoding/json"
	"log"
	"net/http"
)

// ErrorResponse: {"error": "message"}
type ErrorResponse struct {
	Error string `json:"error" example:"Resource not found"`
}

// WriteError sends JSON error. Pass nil for err if no internal error to log.
//
//	api.WriteError(w, http.StatusNotFound, "Workout not found", nil)
//	api.WriteError(w, http.StatusInternalServerError, "DB error", err)
func WriteError(w http.ResponseWriter, status int, message string, err error) {
	if err != nil {
		log.Printf("ERROR [%d] %s: %v", status, message, err)
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(ErrorResponse{Error: message})
}

// WriteSuccess sends JSON success response.
//
//	api.WriteSuccess(w, http.StatusOK, workout)
func WriteSuccess(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}
