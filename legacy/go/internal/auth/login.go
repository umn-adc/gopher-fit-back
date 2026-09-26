package auth

import (
	"database/sql"
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
	if h.Tokens == nil {
		api.WriteError(w, http.StatusInternalServerError, "Authentication is not configured", nil)
		return
	}

	var user User
	if !api.DecodeJSON(w, r, &user) {
		return
	}

	var hashPasswd []byte
	if err := h.DB.QueryRow(`SELECT id, password FROM users WHERE username=?`, user.Username).Scan(&user.ID, &hashPasswd); err != nil {
		if err == sql.ErrNoRows {
			api.WriteError(w, http.StatusNotFound, "User not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Error reading user", err)
		return
	}

	if err := bcrypt.CompareHashAndPassword(hashPasswd, []byte(user.Password)); err != nil {
		api.WriteError(w, http.StatusUnauthorized, "Invalid password", nil)
		return
	}

	tokenString, err := h.Tokens.CreateToken(user)
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
