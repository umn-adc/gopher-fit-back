package profile

import (
	"database/sql"
	"encoding/json"
	"net/http"

	"gopherfit/internal/api"
	"gopherfit/internal/auth"

	"golang.org/x/crypto/bcrypt"
)

type UpdateUserReq struct {
	Username string `json:"username"`
}
type UpdatePassReq struct {
	OldPassword string `json:"old_password"`
	NewPassword string `json:"new_password"`
}

// @Summary Get user profile
// @Tags profile
// @Security BearerAuth
// @Success 200 {object} Profile
// @Router /profile/ [get]
func (h *Handler) handleGetProfile(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
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
		if err != sql.ErrNoRows {
			api.WriteError(w, http.StatusInternalServerError, "Failed to fetch profile", err)
			return
		}
		api.WriteError(w, http.StatusNotFound, "Profile not found", nil)
		return
	}

	if goalsJSON.Valid && goalsJSON.String != "" {
		if err := json.Unmarshal([]byte(goalsJSON.String), &profile.Goals); err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Failed to decode profile goals", err)
			return
		}
	}
	if sportsJSON.Valid && sportsJSON.String != "" {
		if err := json.Unmarshal([]byte(sportsJSON.String), &profile.Sports); err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Failed to decode profile sports", err)
			return
		}
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
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	var profile Profile
	if !api.DecodeJSON(w, r, &profile) {
		return
	}

	goalsJSON, err := json.Marshal(profile.Goals)
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid goals", err)
		return
	}
	sportsJSON, err := json.Marshal(profile.Sports)
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid sports", err)
		return
	}

	res, err := h.DB.Exec(`
		UPDATE profiles
		SET name = ?, age = ?, height = ?, weight = ?, gender = ?, activity_level = ?, goals = ?, sports = ?
		WHERE user_id = ?
	`, profile.Name, profile.Age, profile.Height, profile.Weight, profile.Gender, profile.ActivityLevel, string(goalsJSON), string(sportsJSON), userID)
	if err != nil {
		if api.IsCheckViolation(err) {
			api.WriteError(w, http.StatusBadRequest, "Invalid profile", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to update profile", err)
		return
	}
	if !api.CheckAffected(w, res, "Profile not found") {
		return
	}

	profile.UserID = userID
	api.WriteSuccess(w, http.StatusOK, profile)
}

// @Summary Update username
// @Tags profile
// @Security BearerAuth
// @Param request body UpdateUserReq true "Username update data"
// @Success 200 {object} map[string]any
// @Router /profile/username [put]
func (h *Handler) handleUpdateUsername(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	var req UpdateUserReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	if req.Username == "" {
		api.WriteError(w, http.StatusBadRequest, "Username cannot be empty", nil)
		return
	}

	if !auth.ValidUsername(req.Username) {
		api.WriteError(w, http.StatusBadRequest, "New username is invalid", nil)
		return
	}

	res, err := h.DB.Exec(
		`UPDATE users SET username = ? WHERE id = ?`,
		req.Username,
		userID,
	)

	if err != nil {
		if api.IsUniqueViolation(err) {
			api.WriteError(w, http.StatusConflict, "Username already exists", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to update username", err)
		return
	}
	if !api.CheckAffected(w, res, "User not found") {
		return
	}

	api.WriteSuccess(w, http.StatusOK, map[string]any{
		"username": req.Username,
	})

}

// @Summary Update password
// @Tags profile
// @Security BearerAuth
// @Param request body UpdatePassReq true "Password update data"
// @Success 200 {object} map[string]any
// @Router /profile/password [put]
func (h *Handler) handleUpdatePassword(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	var req UpdatePassReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	if req.OldPassword == "" || req.NewPassword == "" {
		api.WriteError(w, http.StatusBadRequest, "Password fields cannot be empty", nil)
		return
	}

	var currentHash []byte
	err := h.DB.QueryRow(
		`SELECT password FROM users WHERE id = ?`,
		userID,
	).Scan(&currentHash)

	if err != nil {
		if err == sql.ErrNoRows {
			api.WriteError(w, http.StatusNotFound, "User not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to read user", err)
		return
	}

	if err := bcrypt.CompareHashAndPassword(currentHash, []byte(req.OldPassword)); err != nil {
		api.WriteError(w, http.StatusUnauthorized, "Incorrect Password", nil)
		return
	}

	if !auth.ValidPasswd(req.NewPassword) {
		api.WriteError(w, http.StatusBadRequest, "New password is invalid", nil)
		return
	}

	newHash, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcrypt.DefaultCost)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Hashing failed", err)
		return
	}

	res, err := h.DB.Exec(
		`UPDATE users SET password = ? WHERE id = ?`,
		newHash,
		userID,
	)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to update password", err)
		return
	}
	if !api.CheckAffected(w, res, "User not found") {
		return
	}

	api.WriteSuccess(w, http.StatusOK, map[string]any{
		"message": "Password updated successfully",
	})

}
