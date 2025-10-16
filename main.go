package main

import (
	"net/http"

	"gopherfit/endpoints/example"
	"gopherfit/endpoints/practice"

	// "gopherfit/internal/auth"
	// "gopherfit/internal/health"
	// "gopherfit/internal/macros"
	"gopherfit/internal/db"
)

func main() {
	// Initialize the database
	if _, err := db.OpenDB(); err != nil {
		panic(err)
	}
	defer db.CloseDB()

	// here is the base mux
	baseMux := http.NewServeMux()

	// the baseMux will mainly be used like this
	baseMux.Handle("/practice/", practice.GetServeMux())
	baseMux.Handle("/example/", example.GetServeMux())

	// temporary example of defining an endpoint directly on the baseMux
	baseMux.HandleFunc("/api/ping", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"message": "pong"}`))
	})

	println("Listening on port: 3000")
	http.ListenAndServe("localhost:3000", baseMux)
}
