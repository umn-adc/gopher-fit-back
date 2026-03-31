package main

import (
	"net/http"

	"gopherfit/internal/auth"
	"gopherfit/internal/db"
	"gopherfit/internal/middleware"
	"gopherfit/internal/nutrition"
	"gopherfit/internal/profile"
	"gopherfit/internal/social"
	"gopherfit/internal/workouts"

	_ "gopherfit/docs"

	httpSwagger "github.com/swaggo/http-swagger"
)

// @title GopherFit API
// @version 1.0
// @description Fitness tracking API for workouts, nutrition, and user profiles
// @host localhost:3000
// @BasePath /
// @securityDefinitions.apikey BearerAuth
// @in header
// @name Authorization
// @description Enter your JWT token with the Bearer prefix, e.g. "Bearer eyJhbG..."
func main() {
	// Initialize the database
	conn := db.InitDB()
	defer conn.Close()

	baseMux := http.NewServeMux()

	// Auth handler (no JWT middleware needed)
	authHandler := auth.NewHandler(conn)
	baseMux.Handle("/auth/", authHandler.RegisterRoutes())

	// Protected handlers (with JWT middleware)
	profileHandler := profile.NewHandler(conn)
	nutritionHandler := nutrition.NewHandler(conn)
	workoutsHandler := workouts.NewHandler(conn)
	socialHandler := social.NewHandler(conn)

	baseMux.Handle("/profile/", middleware.JWTMiddleware(profileHandler.RegisterRoutes()))
	baseMux.Handle("/nutrition/", middleware.JWTMiddleware(nutritionHandler.RegisterRoutes()))
	baseMux.Handle("/workouts/", middleware.JWTMiddleware(workoutsHandler.RegisterRoutes()))
	baseMux.Handle("/social/", middleware.JWTMiddleware(socialHandler.RegisterRoutes()))

	// Swagger UI
	baseMux.Handle("/swagger/", httpSwagger.Handler(
		httpSwagger.PersistAuthorization(true),
	))

	println("Listening on port: 3000")
	println("Swagger UI: http://localhost:3000/swagger/index.html")
	http.ListenAndServe("localhost:3000", baseMux)
}
