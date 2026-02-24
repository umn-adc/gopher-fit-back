package nutrition

import (
	"net/http"

	"gopherfit/internal/api"
)

// @Summary Update meal item
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param itemId path int true "Item ID"
// @Param request body MealItem true "Meal item data"
// @Success 200 {object} MealItem
// @Router /nutrition/meals/{id}/items/{itemId} [put]
func (h *Handler) updateMealItem(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
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
