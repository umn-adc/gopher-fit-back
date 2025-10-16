package example

import (
	"fmt"
	"net/http"
)

func GetServeMux() *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /example/hello_world", handleHelloWorld)
	mux.HandleFunc("GET /example/evil_endpoint", handleEvilEndpoint)

	return mux
}

func handleHelloWorld(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	switch name {
	case "":
		http.Error(w, "must say your name", http.StatusBadRequest)
	case "none":
		w.Write([]byte("Hello stranger from /example/hello_world"))
	default:
		fmt.Fprintf(w, "Hello %s from /example/hello_world", name)
	}
}

func handleEvilEndpoint(w http.ResponseWriter, r *http.Request) {
	http.Error(w, "you cannot call the evil endpoint", http.StatusForbidden)
}
