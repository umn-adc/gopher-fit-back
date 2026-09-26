package main

import (
	"log"
	"net/http"
	"os"
	"time"

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
	tokens, err := auth.NewTokenService([]byte(os.Getenv("JWT_SECRET")), 24*time.Hour)
	if err != nil {
		log.Fatal("failed to configure authentication: ", err)
	}

	// Initialize the database
	conn, err := db.InitDB()
	if err != nil {
		log.Fatal("failed to initialize database: ", err)
	}
	defer conn.Close()

	baseMux := http.NewServeMux()

	// Auth handler (no JWT middleware needed)
	authHandler := auth.NewHandler(conn, tokens)
	baseMux.Handle("/auth/", authHandler.RegisterRoutes())

	// Protected handlers (with JWT middleware)
	profileHandler := profile.NewHandler(conn)
	nutritionHandler := nutrition.NewHandler(conn)
	workoutsHandler := workouts.NewHandler(conn)
	socialHandler := social.NewHandler(conn)

	baseMux.Handle("/profile/", middleware.JWTMiddleware(tokens, profileHandler.RegisterRoutes()))
	baseMux.Handle("/nutrition/", middleware.JWTMiddleware(tokens, nutritionHandler.RegisterRoutes()))
	baseMux.Handle("/workouts/", middleware.JWTMiddleware(tokens, workoutsHandler.RegisterRoutes()))
	baseMux.Handle("/social/", middleware.JWTMiddleware(tokens, socialHandler.RegisterRoutes()))

	// Swagger UI
	baseMux.Handle("/swagger/", httpSwagger.Handler(
		httpSwagger.PersistAuthorization(true),
	))

	println("Listening on port: 3000")
	println("Swagger UI: http://localhost:3000/swagger/index.html")
	if err := http.ListenAndServe("localhost:3000", baseMux); err != nil {
		log.Fatal("server stopped: ", err)
	}
}
