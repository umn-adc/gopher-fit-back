// Package testutil provides isolated SQLite fixtures and authenticated HTTP requests.
package testutil

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"gopherfit/internal/api"
	"gopherfit/internal/auth"
	"gopherfit/internal/db"
	"gopherfit/internal/middleware"
)

func NewDB(t *testing.T) *sql.DB {
	t.Helper()
	conn, err := db.Open(":memory:")
	if err != nil {
		t.Fatalf("open test database: %v", err)
	}
	t.Cleanup(func() {
		if err := conn.Close(); err != nil {
			t.Errorf("close test database: %v", err)
		}
	})
	return conn
}

func Exec(t *testing.T, conn *sql.DB, query string, args ...any) {
	t.Helper()
	if _, err := conn.Exec(query, args...); err != nil {
		t.Fatalf("prepare fixture: %v", err)
	}
}

type Client struct {
	handler http.Handler
	tokens  *auth.TokenService
}

// NewClient exercises the same JWT middleware used by the application.
func NewClient(t *testing.T, handler http.Handler) *Client {
	t.Helper()
	tokens, err := auth.NewTokenService([]byte("endpoint-test-secret"), time.Hour)
	if err != nil {
		t.Fatalf("configure test authentication: %v", err)
	}
	return &Client{handler: middleware.JWTMiddleware(tokens, handler), tokens: tokens}
}

// Request omits authentication when userID is zero.
func (c *Client) Request(t *testing.T, userID int, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if userID != 0 {
		token, err := c.tokens.CreateToken(auth.User{ID: userID})
		if err != nil {
			t.Fatalf("create test token: %v", err)
		}
		req.Header.Set("Authorization", "Bearer "+token)
	}
	res := httptest.NewRecorder()
	c.handler.ServeHTTP(res, req)
	return res
}

func AssertStatus(t *testing.T, res *httptest.ResponseRecorder, want int) {
	t.Helper()
	if res.Code != want {
		t.Fatalf("status = %d, want %d; body=%s", res.Code, want, res.Body.String())
	}
	if want >= 400 {
		var response api.ErrorResponse
		if res.Header().Get("Content-Type") != "application/json" || json.Unmarshal(res.Body.Bytes(), &response) != nil || response.Error == "" {
			t.Fatalf("expected JSON error response, got %s", res.Body.String())
		}
	}
}
