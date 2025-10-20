package practice

import (
	"fmt"
	"net/http"
)
//says hello to user's name
func handleTeerark(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	switch name {
	case "":
		http.Error(w, "must say your name", http.StatusBadRequest)
	default:
		fmt.Fprintf(w, "Hello %s from teerark", name)
	}
}
