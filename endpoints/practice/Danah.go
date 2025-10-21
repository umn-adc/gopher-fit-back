package practice

import (
	"fmt"
	"net/http"
)


func handleDanah(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	switch name {
	case "":
		http.Error(w, "must say your name", http.StatusBadRequest)
	case "none":
		w.Write([]byte("Hello stranger from Danah\n"))
	default:
		fmt.Fprintf(w, "Hello %s from Danah\n", name)
	}
}
