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
	"net/http"
)

func Handler(w http.ResponseWriter, r *http.Request) {
	switch r.URL.Path {
	case "/api/auth/register":
		handleRegister(w, r)
	case "/api/auth/login":
		handleLogin(w, r)
	default:
		http.Error(w, "not found", http.StatusNotFound)
	}
}
