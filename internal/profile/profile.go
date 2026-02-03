package profile

import (
	"database/sql"
	"encoding/json"
	"net/http"

	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
)

// @Summary Get user profile
// @Tags profile
// @Security BearerAuth
// @Success 200 {object} Profile
// @Router /profile/ [get]
func (h *Handler) handleGetProfile(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	var profile Profile
	var goalsJSON, sportsJSON sql.NullString

	err := h.DB.QueryRow(`
		SELECT user_id, name, age, height, weight, gender, activity_level, goals, sports
		FROM profiles WHERE user_id = ?
	`, userID).Scan(
		&profile.UserID,
		&profile.Name,
		&profile.Age,
		&profile.Height,
		&profile.Weight,
		&profile.Gender,
		&profile.ActivityLevel,
		&goalsJSON,
		&sportsJSON,
	)
	if err != nil {
		api.WriteError(w, http.StatusNotFound, "Profile not found", err)
		return
	}

	if goalsJSON.Valid && goalsJSON.String != "" {
		json.Unmarshal([]byte(goalsJSON.String), &profile.Goals)
	}
	if sportsJSON.Valid && sportsJSON.String != "" {
		json.Unmarshal([]byte(sportsJSON.String), &profile.Sports)
	}

	api.WriteSuccess(w, http.StatusOK, profile)
}

// @Summary Update user profile
// @Tags profile
// @Security BearerAuth
// @Param request body Profile true "Profile data"
// @Success 200 {object} Profile
// @Router /profile/ [put]
func (h *Handler) handleUpdateProfile(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	var profile Profile
	if err := json.NewDecoder(r.Body).Decode(&profile); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	goalsJSON, _ := json.Marshal(profile.Goals)
	sportsJSON, _ := json.Marshal(profile.Sports)

	_, err := h.DB.Exec(`
		UPDATE profiles
		SET name = ?, age = ?, height = ?, weight = ?, gender = ?, activity_level = ?, goals = ?, sports = ?
		WHERE user_id = ?
	`, profile.Name, profile.Age, profile.Height, profile.Weight, profile.Gender, profile.ActivityLevel, string(goalsJSON), string(sportsJSON), userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to update profile", err)
		return
	}

	profile.UserID = userID
	api.WriteSuccess(w, http.StatusOK, profile)
}
