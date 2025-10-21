package practice

import (
	"fmt"
	"net/http"
)

// handleMamta handles requests to the /practice/mamta endpoint
// It looks for a "name" query parameter with specific responses depending on its value
func handleMamta(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	switch name {
	case "":
		http.Error(w, "must say your name", http.StatusBadRequest)
	case "none":
		w.Write([]byte("Hello stranger from Mamta\n"))
	default:
		fmt.Fprintf(w, "Hello %s from Mamta\n", name)
	}
}