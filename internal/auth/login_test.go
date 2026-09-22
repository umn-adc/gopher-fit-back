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

	"golang.org/x/crypto/bcrypt"
)

func TestLoginWorksAfterLegacyPasswordMigration(t *testing.T) {
	path := filepath.Join(t.TempDir(), "legacy-login.db")
	legacy, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatalf("open legacy database: %v", err)
	}
	hash, err := bcrypt.GenerateFromPassword([]byte("Password1!"), bcrypt.MinCost)
	if err != nil {
		legacy.Close()
		t.Fatalf("hash password: %v", err)
	}
	_, err = legacy.Exec(`
		CREATE TABLE users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT UNIQUE NOT NULL,
			password TEXT NOT NULL
		);
		INSERT INTO users (username, password) VALUES (?, ?)
	`, "legacy-user", string(hash))
	if err != nil {
		legacy.Close()
		t.Fatalf("create legacy user: %v", err)
	}
	if err := legacy.Close(); err != nil {
		t.Fatalf("close legacy database: %v", err)
	}

	conn, err := appdb.Open(path)
	if err != nil {
		t.Fatalf("migrate legacy database: %v", err)
	}
	defer conn.Close()
	tokens, err := NewTokenService([]byte("test-secret"), time.Hour)
	if err != nil {
		t.Fatalf("create token service: %v", err)
	}
	handler := NewHandler(conn, tokens)

	body, err := json.Marshal(LoginRequest{Username: "legacy-user", Password: "Password1!"})
	if err != nil {
		t.Fatalf("marshal login: %v", err)
	}
	req := httptest.NewRequest(http.MethodPost, "/auth/login", bytes.NewReader(body))
	res := httptest.NewRecorder()
	handler.RegisterRoutes().ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d; body=%s", res.Code, http.StatusOK, res.Body.String())
	}
	var response AuthResponse
	if err := json.NewDecoder(res.Body).Decode(&response); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	if response.Token == "" || response.Username != "legacy-user" {
		t.Fatalf("unexpected login response: %+v", response)
	}
}
