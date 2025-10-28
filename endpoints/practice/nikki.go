package practice

import (
	"fmt"
	"net/http"
)

// The function below is supposed to get the name from the URL query and send a response message accordingly
func handleNikki(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	switch name {
	case "":
		http.Error(w, "must say your name", http.StatusBadRequest)
	case "none":
		w.Write([]byte("Hello " + name + " from Nikki"))
	default:
		fmt.Fprintf(w, "Hello %s from Nikki", name)
	}
}
