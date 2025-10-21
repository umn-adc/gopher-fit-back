package practice

import (
	"fmt"
	"net/http"
)

// handleDaniel handles the Daniel endpoint:
// expects URL parameter "name" and responds with
// "Hello <name> from Daniel".
func handleDaniel(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	if name == "" {
		http.Error(w, "missing 'name' parameter", http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprintf(w, "Hello %s from Daniel", name)
}
