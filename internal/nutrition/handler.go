package nutrition

import (
	"database/sql"
	"net/http"
)

type Handler struct {
	DB *sql.DB
}

func NewHandler(db *sql.DB) *Handler {
	return &Handler{DB: db}
}

func (h *Handler) RegisterRoutes() *http.ServeMux {
	r := http.NewServeMux()

	// Meal CRUD
	r.HandleFunc("GET /nutrition/meals", h.getUserMeals)
	r.HandleFunc("POST /nutrition/meals", h.addMeal)
	r.HandleFunc("GET /nutrition/meals/{id}", h.getMeal)
	r.HandleFunc("PUT /nutrition/meals/{id}", h.updateMeal)
	r.HandleFunc("DELETE /nutrition/meals/{id}", h.deleteMeal)

	// Meal Item CRUD
	r.HandleFunc("POST /nutrition/meals/{id}/items", h.addMealItem)
	r.HandleFunc("PUT /nutrition/meals/{id}/items/{itemId}", h.updateMealItem)
	r.HandleFunc("DELETE /nutrition/meals/{id}/items/{itemId}", h.deleteMealItem)

	// Macro Goals
	r.HandleFunc("GET /nutrition/macros", h.getMacroGoals)
	r.HandleFunc("PUT /nutrition/macros", h.updateMacroGoals)
	r.HandleFunc("POST /nutrition/macros", h.addMacro)

	return r
}
