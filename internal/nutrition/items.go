package nutrition

import (
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
}
