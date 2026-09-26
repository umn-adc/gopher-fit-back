package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"gopherfit/internal/api"
	"gopherfit/internal/auth"

	"github.com/golang-jwt/jwt/v5"
)

func TestJWTMiddlewareRejectsMalformedAuthorization(t *testing.T) {
	tokens, err := auth.NewTokenService([]byte("test-secret"), time.Hour)
	if err != nil {
		t.Fatalf("NewTokenService() error = %v", err)
	}

	values := []string{"", "x", "Basic abc", "Bearer", "Bearer a b", "Bearer invalid"}
	for _, value := range values {
		t.Run(value, func(t *testing.T) {
			nextCalled := false
			handler := JWTMiddleware(tokens, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
				nextCalled = true
			}))
			req := httptest.NewRequest(http.MethodGet, "/protected", nil)
			if value != "" {
				req.Header.Set("Authorization", value)
			}
			res := httptest.NewRecorder()

			handler.ServeHTTP(res, req)

			if res.Code != http.StatusUnauthorized {
				t.Fatalf("status = %d, want %d", res.Code, http.StatusUnauthorized)
			}
			if nextCalled {
				t.Fatal("next handler was called")
			}
			if got := res.Header().Get("Content-Type"); got != "application/json" {
				t.Fatalf("Content-Type = %q, want application/json", got)
			}
		})
	}
}

func TestJWTMiddlewareAddsAuthenticatedUserToContext(t *testing.T) {
	tokens, err := auth.NewTokenService([]byte("test-secret"), time.Hour)
	if err != nil {
		t.Fatalf("NewTokenService() error = %v", err)
	}
	token, err := tokens.CreateToken(auth.User{ID: 27, Username: "goldy"})
	if err != nil {
		t.Fatalf("CreateToken() error = %v", err)
	}

	handler := JWTMiddleware(tokens, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := r.Context().Value(api.CtxUserIDKey).(int)
		if !ok || userID != 27 {
			t.Errorf("context user ID = (%d, %v), want (27, true)", userID, ok)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	res := httptest.NewRecorder()

	handler.ServeHTTP(res, req)

	if res.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want %d", res.Code, http.StatusNoContent)
	}
}

func TestJWTMiddlewareRejectsExpiredAndInvalidSignatureTokens(t *testing.T) {
	tokens, err := auth.NewTokenService([]byte("test-secret"), time.Hour)
	if err != nil {
		t.Fatalf("NewTokenService() error = %v", err)
	}
	otherTokens, err := auth.NewTokenService([]byte("other-secret"), time.Hour)
	if err != nil {
		t.Fatalf("NewTokenService() with other secret error = %v", err)
	}
	wrongSignature, err := otherTokens.CreateToken(auth.User{ID: 1, Username: "gopher"})
	if err != nil {
		t.Fatalf("CreateToken() with other secret error = %v", err)
	}
	expired, err := jwt.NewWithClaims(jwt.SigningMethodHS256, &auth.Claims{
		ID: 1,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(-time.Minute)),
		},
	}).SignedString([]byte("test-secret"))
	if err != nil {
		t.Fatalf("sign expired token: %v", err)
	}

	for name, token := range map[string]string{
		"expired":         expired,
		"wrong signature": wrongSignature,
	} {
		t.Run(name, func(t *testing.T) {
			handler := JWTMiddleware(tokens, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
				t.Fatal("next handler was called")
			}))
			req := httptest.NewRequest(http.MethodGet, "/protected", nil)
			req.Header.Set("Authorization", "Bearer "+token)
			res := httptest.NewRecorder()

			handler.ServeHTTP(res, req)

			if res.Code != http.StatusUnauthorized {
				t.Fatalf("status = %d, want %d", res.Code, http.StatusUnauthorized)
			}
		})
	}
}

func TestJWTMiddlewareRequiresConfiguredService(t *testing.T) {
	handler := JWTMiddleware(nil, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		t.Fatal("next handler was called")
	}))
	res := httptest.NewRecorder()
	handler.ServeHTTP(res, httptest.NewRequest(http.MethodGet, "/protected", nil))
	if res.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, want %d", res.Code, http.StatusInternalServerError)
	}
}
