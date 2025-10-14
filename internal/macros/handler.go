// internal/macros/handler.go
//
// ------------------------------------------------------------
// MACROS HANDLER (Router only)
// ------------------------------------------------------------
//
// This file defines which functions handle each HTTP route for macros.
// Actual logic for GET and POST lives in:
//   internal/macros/get.go
//   internal/macros/post.go
//
// New contributors should NOT write logic here — only route methods.
//
// ------------------------------------------------------------

package macros

import (
	"net/http"
)

func Handler(w http.ResponseWriter, r *http.Request) {
	switch {
	case r.URL.Path == "/api/macros" && r.Method == http.MethodGet:
		handleGetMacros(w, r)
	case r.URL.Path == "/api/macros" && r.Method == http.MethodPost:
		handlePostMacros(w, r)
	default:
		http.Error(w, "not found", http.StatusNotFound)
	}
}
