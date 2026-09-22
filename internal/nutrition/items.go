package nutrition

import (
	"net/http"
	"strings"

	"gopherfit/internal/api"
)

// @Summary Update meal item
// @Description Updates an item only within a meal owned by the caller. IDs come from the path; body IDs are ignored. Name must be nonblank and nutrition values must be nonnegative integers.
// @Tags nutrition
// @Security BearerAuth
// @Accept json
// @Produce json
// @Param id path int true "Meal ID"
// @Param itemId path int true "Item ID"
// @Param request body MealItem true "Meal item data"
// @Success 200 {object} MealItem
// @Failure 400 {object} api.ErrorResponse "Invalid IDs, JSON, name, or nutrition values"
// @Failure 401 {object} api.ErrorResponse "Authentication required"
// @Failure 404 {object} api.ErrorResponse "Meal item missing or not owned by caller"
// @Failure 500 {object} api.ErrorResponse "Database failure"
// @Router /nutrition/meals/{id}/items/{itemId} [put]
func (h *Handler) updateMealItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	mealID, ok := api.PositivePathInt(w, r, "id")
	if !ok {
		return
	}

	itemID, ok := api.PositivePathInt(w, r, "itemId")
	if !ok {
		return
	}

	var req MealItem
	if !api.DecodeJSON(w, r, &req) {
		return
	}
	if strings.TrimSpace(req.Name) == "" || req.Calories < 0 || req.Protein < 0 || req.Carbs < 0 || req.Fat < 0 {
		api.WriteError(w, http.StatusBadRequest, "Name is required and nutrition values must be nonnegative", nil)
		return
	}

	res, err := h.DB.ExecContext(r.Context(), `
		UPDATE meal_items
		SET name = ?,
		    calories = ?,
		    protein = ?,
		    carbs = ?,
		    fat = ?
		WHERE id = ?
		AND meal_id = ?
		AND EXISTS (SELECT 1 FROM meals WHERE id = meal_items.meal_id AND user_id = ?)`,
		req.Name, req.Calories, req.Protein, req.Carbs, req.Fat,
		itemID, mealID, userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to update meal item", err)
		return
	}

	if !api.CheckAffected(w, res, "Meal item not found") {
		return
	}

	req.ID = itemID
	req.MealID = mealID
	api.WriteSuccess(w, http.StatusOK, req)
}

// @Summary Delete meal item
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param itemId path int true "Item ID"
// @Success 204 "No Content"
// @Router /nutrition/meals/{id}/items/{itemId} [delete]
func (h *Handler) deleteMealItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	mealID, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	itemID, ok := api.PathInt(w, r, "itemId")
	if !ok {
		return
	}

	res, err := h.DB.Exec(`
		DELETE FROM meal_items WHERE id = ? AND meal_id IN (SELECT id FROM meals WHERE id = ? AND user_id = ?)`,
		itemID, mealID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete meal item", err)
		return
	}

	if !api.CheckAffected(w, res, "Meal item not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
