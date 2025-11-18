package middleware

import (
	"context"
	// "fmt"
	"net/http"

	"gopherfit/internal/auth"
)

/*
* Middleware wrapper for our endpoints
* @param Handler for our endpoint with type http.ServeMux or http.Handler
*/
func JWTMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			tokenString := r.Header.Get("Authorization")
			if tokenString == "" {
				http.Error(w, "Requires JWT Token", http.StatusUnauthorized)
				return
			}

			// Retrieve the token string
			tokenString = tokenString[len("Bearer "):]
			id, username, err := auth.VerifyToken(tokenString)
			if err != nil {
				http.Error(w, "Invalid JWT Token", http.StatusUnauthorized)
				return
			}
			// Create context to pass userID and username to our next handler
			ctx := context.WithValue(r.Context(), CtxUserIDKey, id)
			ctx = context.WithValue(ctx, CtxUsernameKey, username)

			// You can retrieve id and username from the context by:
				// import "gopherfit/internal/middleware"
				// id := r.Context().Value(CtxUserIDKey)
				// username := r.Context().Value(CtxUsernameKey)
			// Check internal/middleware/models.go for any context keys

			next.ServeHTTP(w, r.WithContext(ctx))
    	})
}
