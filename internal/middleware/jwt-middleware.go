package middleware

import (
	"context"
	"net/http"
	"strings"

	"gopherfit/internal/api"
	"gopherfit/internal/auth"
)

// JWTMiddleware verifies a Bearer token and adds the authenticated user ID to
// the request context.
func JWTMiddleware(tokens *auth.TokenService, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if tokens == nil {
			api.WriteError(w, http.StatusInternalServerError, "Authentication is not configured", nil)
			return
		}

		parts := strings.Fields(r.Header.Get("Authorization"))
		if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") || parts[1] == "" {
			api.WriteError(w, http.StatusUnauthorized, "Requires Bearer JWT token", nil)
			return
		}

		id, _, err := tokens.VerifyToken(parts[1])
		if err != nil {
			api.WriteError(w, http.StatusUnauthorized, "Invalid JWT token", nil)
			return
		}

		ctx := context.WithValue(r.Context(), api.CtxUserIDKey, id)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
