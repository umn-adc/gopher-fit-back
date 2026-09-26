package auth

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// TokenService signs and verifies application JWTs with an injected secret.
type TokenService struct {
	secret []byte
	ttl    time.Duration
}

func NewTokenService(secret []byte, ttl time.Duration) (*TokenService, error) {
	if len(secret) == 0 {
		return nil, fmt.Errorf("JWT secret cannot be empty")
	}
	if ttl <= 0 {
		return nil, fmt.Errorf("JWT TTL must be positive")
	}

	secretCopy := append([]byte(nil), secret...)
	return &TokenService{secret: secretCopy, ttl: ttl}, nil
}

func (s *TokenService) CreateToken(u User) (string, error) {
	now := time.Now()
	claims := &Claims{
		ID:       u.ID,
		Username: u.Username,
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(s.ttl)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(s.secret)
	if err != nil {
		return "", fmt.Errorf("sign token: %w", err)
	}
	return tokenString, nil
}

func (s *TokenService) VerifyToken(tokenString string) (int, string, error) {
	claims := &Claims{}
	token, err := jwt.ParseWithClaims(
		tokenString,
		claims,
		func(token *jwt.Token) (any, error) {
			if token.Method != jwt.SigningMethodHS256 {
				return nil, fmt.Errorf("unexpected signing method %s", token.Method.Alg())
			}
			return s.secret, nil
		},
		jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}),
	)
	if err != nil {
		return 0, "", fmt.Errorf("parse token: %w", err)
	}
	if !token.Valid || claims.ID <= 0 {
		return 0, "", fmt.Errorf("invalid token")
	}
	return claims.ID, claims.Username, nil
}
