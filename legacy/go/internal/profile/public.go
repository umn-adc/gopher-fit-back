package profile

import (
	"database/sql"
	"errors"
	"net/http"

	"gopherfit/internal/api"
)

// @Summary Look up a user's public username
// @Description Returns only user_id and username. Requires authentication. Private attributes remain available only through GET /profile/ for the caller.
// @Tags profile
// @Security BearerAuth
// @Produce json
// @Param id path int true "Positive user ID"
// @Success 200 {object} PublicProfile
// @Failure 400 {object} api.ErrorResponse "Invalid user ID"
// @Failure 401 {object} api.ErrorResponse "Authentication required"
// @Failure 404 {object} api.ErrorResponse "User not found"
// @Failure 500 {object} api.ErrorResponse "Database failure"
// @Router /profile/{id} [get]
func (h *Handler) handleGetPublicProfile(w http.ResponseWriter, r *http.Request) {
	if _, ok := api.GetUserID(w, r); !ok {
		return
	}
	id, ok := api.PositivePathInt(w, r, "id")
	if !ok {
		return
	}

	var public PublicProfile
	err := h.DB.QueryRowContext(r.Context(), `SELECT id, username FROM users WHERE id = ?`, id).
		Scan(&public.UserID, &public.Username)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			api.WriteError(w, http.StatusNotFound, "User not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch user", err)
		return
	}
	api.WriteSuccess(w, http.StatusOK, public)
}
