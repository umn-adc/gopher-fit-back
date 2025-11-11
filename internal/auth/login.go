package auth

import (
	"database/sql"
	"encoding/json"
	"net/http"

	"golang.org/x/crypto/bcrypt"
)

// handleLogin handles POST /api/auth/login requests.
func (h *Handler) handleLogin(w http.ResponseWriter, r *http.Request) {
	// Read in username and password from JSON
	var user User
	if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	DB := h.DB

	var hashPasswd string
	if err := DB.QueryRow(`SELECT id, password FROM users
		WHERE username=?
	`, user.Username).Scan(&user.ID, &hashPasswd); err != nil {
		if err == sql.ErrNoRows {
			http.Error(w, "Non-existant user", http.StatusNotFound)
			return
		}
		http.Error(w, "Error reading user", http.StatusInternalServerError)
		return
	}

	// Invalid password
	if err := bcrypt.CompareHashAndPassword([]byte(hashPasswd), []byte(user.Password)); err != nil {
		http.Error(w, "Invalid Password", http.StatusUnauthorized)
		return
	}

	// Valid user
	tokenString, err := createToken(user)
	if err != nil {
		http.Error(w, "Error creating token", http.StatusInternalServerError)
		return
	}

	// Create our response
	response := struct {
		Token string `json:"token"`
		UserID  int
		Username string `json:"username"`
	}{
		Token: tokenString,
		UserID: user.ID,
		Username: user.Username,
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
