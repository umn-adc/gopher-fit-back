package auth

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	appdb "gopherfit/internal/db"
)

func TestRegisterRollsBackUserWhenProfileCreationFails(t *testing.T) {
	handler, conn := newTestHandler(t)
	defer conn.Close()

	payload := User{
		Username:      "rollback-user",
		Password:      "Password1!",
		Name:          "Rollback User",
		Gender:        "invalid-gender",
		ActivityLevel: "Sedentary",
	}
	res := performRegister(t, handler, payload)
	if res.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d; body=%s", res.Code, http.StatusBadRequest, res.Body.String())
	}

	var users int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM users WHERE username = ?`, payload.Username).Scan(&users); err != nil {
		t.Fatalf("count users: %v", err)
	}
	if users != 0 {
		t.Fatalf("user count = %d, want 0 after rollback", users)
	}
}

func TestRegisterStoresBlobHashAndRejectsDuplicateUsername(t *testing.T) {
	handler, conn := newTestHandler(t)
	defer conn.Close()

	payload := User{
		Username:      "new-user",
		Password:      "Password1!",
		Name:          "New User",
		Age:           21,
		Height:        170,
		Weight:        70,
		Gender:        "Other",
		ActivityLevel: "Moderately Active",
		Goals:         []string{"Build Muscle"},
		Sports:        []string{"Basketball"},
	}
	res := performRegister(t, handler, payload)
	if res.Code != http.StatusCreated {
		t.Fatalf("status = %d, want %d; body=%s", res.Code, http.StatusCreated, res.Body.String())
	}

	var storageType string
	if err := conn.QueryRow(`SELECT typeof(password) FROM users WHERE username = ?`, payload.Username).Scan(&storageType); err != nil {
		t.Fatalf("read password storage type: %v", err)
	}
	if storageType != "blob" {
		t.Fatalf("password storage type = %q, want blob", storageType)
	}

	duplicate := performRegister(t, handler, payload)
	if duplicate.Code != http.StatusConflict {
		t.Fatalf("duplicate status = %d, want %d; body=%s", duplicate.Code, http.StatusConflict, duplicate.Body.String())
	}
}

func newTestHandler(t *testing.T) (*Handler, *sql.DB) {
	t.Helper()
	conn, err := appdb.Open(filepath.Join(t.TempDir(), "auth.db"))
	if err != nil {
		t.Fatalf("open test database: %v", err)
	}
	tokens, err := NewTokenService([]byte("test-secret"), time.Hour)
	if err != nil {
		conn.Close()
		t.Fatalf("create token service: %v", err)
	}
	return NewHandler(conn, tokens), conn
}

func performRegister(t *testing.T, handler *Handler, payload User) *httptest.ResponseRecorder {
	t.Helper()
	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}
	req := httptest.NewRequest(http.MethodPost, "/auth/register", bytes.NewReader(body))
	res := httptest.NewRecorder()
	handler.RegisterRoutes().ServeHTTP(res, req)
	return res
}
