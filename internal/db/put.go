package internal 

import (
	"net/http"
	"encoding/json"
	"database/sql"
	"github.com/golang-jwt/jwt/v5"
)

func handlePutUserInfo (w http.ResponseWriter, r *http.Request) {
	var details auth.UserDetails

	if err := json.NewDecoder(r.Body).Decode(&userDetails); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	query := `
		UPDATE UserDetails
		Set name = ?, age = ?, height = ?, weight = ?, gender = ?, activity_level = ?
		Where user_id = ? `

	result, err := h.DB.Exec(query,
		details.Name,
		details.Age,
		details.Height,
		details.Weight,
		details.Gender,
		details.ActivityLevel,
		userID,
	)
	
	if err != nil {
		http.Error(w, "failed to update details", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{
		"message": "user details added successfully",
	})
}