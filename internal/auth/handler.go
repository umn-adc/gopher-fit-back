// internal/auth/handler.go
//
// ------------------------------------------------------------
// AUTH HANDLER (Router only)
// ------------------------------------------------------------
//
// This file defines which functions handle each HTTP route for auth.
// Actual logic for register and login lives in:
//   internal/auth/register.go
//   internal/auth/login.go
//
// New contributors should NOT write logic here — only route methods.
//
// ------------------------------------------------------------

package auth

import (
	"database/sql"
	"net/http"
)

type Handler struct {
	DB     *sql.DB
	Tokens *TokenService
}

func NewHandler(db *sql.DB, tokens *TokenService) *Handler {
	return &Handler{DB: db, Tokens: tokens}
}

func (h *Handler) RegisterRoutes() *http.ServeMux {
	r := http.NewServeMux()

	r.HandleFunc("POST /auth/register", h.handleRegister)

	r.HandleFunc("POST /auth/login", h.handleLogin)

	return r
}
