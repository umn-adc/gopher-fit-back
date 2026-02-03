package profile

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

	r.HandleFunc("GET /profile/", h.handleGetProfile)
	r.HandleFunc("PUT /profile/", h.handleUpdateProfile)

	return r
}
