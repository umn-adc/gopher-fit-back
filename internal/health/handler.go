// internal/health/handler.go
//
// ------------------------------------------------------------
// HEALTH HANDLER (Router only)
// ------------------------------------------------------------
//
// This file defines which functions handle each HTTP route for health.
// Actual logic for GET and POST lives in:
//   internal/health/get.go
//   internal/health/post.go
//
// New contributors should NOT write logic here — only route methods.
//
// ------------------------------------------------------------

package health

import (
	"net/http"
)

func Handler(w http.ResponseWriter, r *http.Request) {
	switch {
	case r.URL.Path == "/api/health" && r.Method == http.MethodGet:
		handleGetHealth(w, r)
	case r.URL.Path == "/api/health" && r.Method == http.MethodPost:
		handlePostHealth(w, r)
	default:
		http.Error(w, "not found", http.StatusNotFound)
	}
}
