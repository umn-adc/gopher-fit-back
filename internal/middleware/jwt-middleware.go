package middleware

import (
	"context"
	"net/http"

	"gopherfit/internal/api"
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

		tokenString = tokenString[len("Bearer "):]
		id, _, err := auth.VerifyToken(tokenString)
		if err != nil {
			http.Error(w, "Invalid JWT Token", http.StatusUnauthorized)
			return
		}

		ctx := context.WithValue(r.Context(), api.CtxUserIDKey, id)

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
