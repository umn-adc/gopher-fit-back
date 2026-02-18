package nutrition

import (
	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
	"net/http"
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
	// TODO: Implement
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	mealID := r.PathValue("id")
	if mealID == "" {
		api.WriteError(w, http.StatusBadRequest, "invalid id", nil)
		return
	}

	itemID := r.PathValue("itemId")
	if itemID == "" {
		api.WriteError(w, http.StatusBadRequest, "invalid id", nil)
		return
	}

	query := `DELETE FROM meal_items where id = ? AND meal_id in (SELECT id FROM meals WHERE id = ? AND user_id = ?)`

	res, err := h.DB.Exec(query, itemID, mealID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete meal item", err)
		return
	}

	rowsAffected, err := res.RowsAffected()
	if err != nil || rowsAffected == 0 {
		api.WriteError(w, http.StatusNotFound, "meal item not found", err)
		return

	}

	w.WriteHeader(http.StatusNoContent)

}
