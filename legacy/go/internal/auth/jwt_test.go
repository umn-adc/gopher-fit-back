package auth

import (
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

func TestTokenServiceRoundTrip(t *testing.T) {
	service, err := NewTokenService([]byte("test-secret"), time.Hour)
	if err != nil {
		t.Fatalf("NewTokenService() error = %v", err)
	}

	token, err := service.CreateToken(User{ID: 42, Username: "gopher"})
	if err != nil {
		t.Fatalf("CreateToken() error = %v", err)
	}
	id, username, err := service.VerifyToken(token)
	if err != nil {
		t.Fatalf("VerifyToken() error = %v", err)
	}
	if id != 42 || username != "gopher" {
		t.Fatalf("verified claims = (%d, %q), want (42, gopher)", id, username)
	}
}

func TestTokenServiceRejectsInvalidTokens(t *testing.T) {
	service, err := NewTokenService([]byte("test-secret"), time.Hour)
	if err != nil {
		t.Fatalf("NewTokenService() error = %v", err)
	}

	tests := map[string]string{
		"expired": signTestToken(t, jwt.SigningMethodHS256, []byte("test-secret"), Claims{
			ID: 1,
			RegisteredClaims: jwt.RegisteredClaims{
				ExpiresAt: jwt.NewNumericDate(time.Now().Add(-time.Minute)),
			},
		}),
		"wrong secret": signTestToken(t, jwt.SigningMethodHS256, []byte("other-secret"), Claims{
			ID: 1,
			RegisteredClaims: jwt.RegisteredClaims{
				ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
			},
		}),
		"wrong algorithm": signTestToken(t, jwt.SigningMethodHS384, []byte("test-secret"), Claims{
			ID: 1,
			RegisteredClaims: jwt.RegisteredClaims{
				ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
			},
		}),
	}

	for name, token := range tests {
		t.Run(name, func(t *testing.T) {
			if _, _, err := service.VerifyToken(token); err == nil {
				t.Fatal("VerifyToken() error = nil, want error")
			}
		})
	}
}

func TestNewTokenServiceValidatesConfiguration(t *testing.T) {
	if _, err := NewTokenService(nil, time.Hour); err == nil {
		t.Fatal("NewTokenService(nil secret) error = nil, want error")
	}
	if _, err := NewTokenService([]byte("secret"), 0); err == nil {
		t.Fatal("NewTokenService(zero TTL) error = nil, want error")
	}
}

func signTestToken(t *testing.T, method jwt.SigningMethod, secret []byte, claims Claims) string {
	t.Helper()
	token, err := jwt.NewWithClaims(method, &claims).SignedString(secret)
	if err != nil {
		t.Fatalf("sign test token: %v", err)
	}
	return token
}
