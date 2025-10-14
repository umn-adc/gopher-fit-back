package main

import (
	"net/http"

	"gopherfit/endpoints/example"
	"gopherfit/internal/auth"
	"gopherfit/internal/health"
	"gopherfit/internal/macros"
	"gopherfit/internal/db"
)

func main() {
	// Initialize the database
	if _, err := db.OpenDB(); err != nil {
		panic(err)
	}
	defer db.CloseDB()

	baseMux := http.NewServeMux()

	// EXAMPLE ENDPOINTS
	baseMux.Handle("/example/", example.GetServeMux())
	baseMux.HandleFunc("/api/ping", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"message": "pong"}`))
	})

	// APP ENDPOINTS
	baseMux.HandleFunc("/api/auth/", auth.Handler)
	baseMux.HandleFunc("/api/macros", macros.Handler)
	baseMux.HandleFunc("/api/health", health.Handler)

	println("Listening on port: 3000")
	http.ListenAndServe("localhost:3000", baseMux)
}
