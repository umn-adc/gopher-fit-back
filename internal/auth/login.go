package auth

import (
	"database/sql"
	"encoding/json"
	"net/http"

	"gopherfit/internal/api"

	"golang.org/x/crypto/bcrypt"
)

// @Summary Login user
// @Tags auth
// @Param request body LoginRequest true "Login credentials"
// @Success 200 {object} AuthResponse
// @Router /auth/login [post]
func (h *Handler) handleLogin(w http.ResponseWriter, r *http.Request) {
	var user User
	if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	var hashPasswd string
	if err := h.DB.QueryRow(`SELECT id, password FROM users WHERE username=?`, user.Username).Scan(&user.ID, &hashPasswd); err != nil {
		if err == sql.ErrNoRows {
			api.WriteError(w, http.StatusNotFound, "User not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Error reading user", err)
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(hashPasswd), []byte(user.Password)); err != nil {
		api.WriteError(w, http.StatusUnauthorized, "Invalid password", nil)
		return
	}

	tokenString, err := createToken(user)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error creating token", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, map[string]any{
		"token":    tokenString,
		"user_id":  user.ID,
		"username": user.Username,
	})
}
