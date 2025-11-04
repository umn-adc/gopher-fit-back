package nutrition

import (
	"net/http"
	"database/sql" 
)

type Handler struct {
	DB *sql.DB
}

func NewHandler(db *sql.DB) *Handler {
	return &Handler{DB: db}
}

func (h *Handler) RegisterRoutes() *http.ServeMux {
	r := http.NewServeMux()

	r.HandleFunc("POST /nutrition/meals", h.addMeal)
	r.HandleFunc("POST /nutrition/meals/{id}/items", h.addMealItem)

	r.HandleFunc("GET /nutrition/goals", h.getGoals)

	return r
}
