package nutrition

import (
	"encoding/json"
	"net/http"

	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
)

// @Summary Add macro goals
// @Tags nutrition
// @Security BearerAuth
// @Param request body MacroGoals true "Macro goals"
// @Success 201 {object} MacroGoals
// @Router /nutrition/macros [post]
func (h *Handler) addMacro(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	var goals MacroGoals
	if err := json.NewDecoder(r.Body).Decode(&goals); err != nil {
		api.WriteError(w, http.StatusBadRequest, "invalid JSON", err)
		return
	}

	_, err := h.DB.Exec(`
		INSERT INTO macro_goals (user_id, calories_target, protein_target, carbs_target, fat_target)
		VALUES (?, ?, ?, ?, ?)
	`, userID, goals.CaloriesTarget, goals.ProteinTarget, goals.CarbsTarget, goals.FatTarget)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert macro goals", err)
		return
	}

	goals.UserID = userID
	api.WriteSuccess(w, http.StatusCreated, goals)
}

// @Summary Get macro goals
// @Tags nutrition
// @Security BearerAuth
// @Success 200 {object} MacroGoals
// @Router /nutrition/macros [get]
func (h *Handler) getMacroGoals(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	var goals MacroGoals
	err := h.DB.QueryRow(`SELECT user_id, calories_target, protein_target, carbs_target, fat_target FROM macro_goals WHERE user_id = ?`, userID).
		Scan(&goals.UserID, &goals.CaloriesTarget, &goals.ProteinTarget, &goals.CarbsTarget, &goals.FatTarget)
	if err != nil {
		api.WriteError(w, http.StatusNotFound, "Macro goals not found", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, goals)
}

// @Summary Update macro goals
// @Tags nutrition
// @Security BearerAuth
// @Param request body MacroGoals true "Macro goals"
// @Success 200 {object} MacroGoals
// @Router /nutrition/macros [put]
func (h *Handler) updateMacroGoals(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	var goals MacroGoals
	if err := json.NewDecoder(r.Body).Decode(&goals); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	_, err := h.DB.Exec(`
		INSERT INTO macro_goals (user_id, calories_target, protein_target, carbs_target, fat_target)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(user_id) DO UPDATE SET
			calories_target = excluded.calories_target,
			protein_target = excluded.protein_target,
			carbs_target = excluded.carbs_target,
			fat_target = excluded.fat_target
	`, userID, goals.CaloriesTarget, goals.ProteinTarget, goals.CarbsTarget, goals.FatTarget)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error updating macro goals", err)
		return
	}

	goals.UserID = userID
	api.WriteSuccess(w, http.StatusOK, goals)
}
