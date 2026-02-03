package nutrition

import (
	"net/http"
)

// @Summary Get macro goals
// @Tags nutrition
// @Security BearerAuth
// @Success 200 {object} MacroGoals
// @Router /nutrition/macros [get]
func (h *Handler) getMacroGoals(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}

// @Summary Update macro goals
// @Tags nutrition
// @Security BearerAuth
// @Param request body MacroGoals true "Macro goals"
// @Success 200 {object} MacroGoals
// @Router /nutrition/macros [put]
func (h *Handler) updateMacroGoals(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}
