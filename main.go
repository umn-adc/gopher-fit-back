package main

import (
	"net/http"

	"gopherfit/endpoints/example"
	"gopherfit/endpoints/practice"
	"gopherfit/internal/auth"

	// "gopherfit/internal/auth"
	// "gopherfit/internal/workouts"
	"gopherfit/internal/nutrition"
	"gopherfit/internal/workouts"
	// "gopherfit/internal/social"
	"gopherfit/internal/db"
)

func main() {
	// Initialize the database
	conn := db.InitDB()
	defer conn.Close()

	// here is the base mux
	baseMux := http.NewServeMux()

	// the baseMux will mainly be used like this
	baseMux.Handle("/practice/", practice.GetServeMux())
	baseMux.Handle("/example/", example.GetServeMux())

	authHandler := auth.NewHandler(conn)
	baseMux.Handle("/auth/", authHandler.RegisterRoutes())

	nutritionHandler := nutrition.NewHandler(conn)
	workoutsHandler := workouts.NewHandler(conn)
	
	baseMux.Handle("/nutrition/", nutritionHandler.RegisterRoutes())
	baseMux.Handle("/workouts/", workoutsHandler.RegisterRoutes())

	println("Listening on port: 3000")
	http.ListenAndServe("localhost:3000", baseMux)
}
