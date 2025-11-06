// internal/auth/model.go
//
// ------------------------------------------------------------
// AUTH MODEL (Data Structures)
// ------------------------------------------------------------
//
// This file defines structs used across the auth package.
// These represent request/response bodies or database records.
//
// ------------------------------------------------------------

package auth

import (
	"github.com/golang-jwt/jwt/v5"
)

type User struct {
	ID       int    `json:"id"`
	Username string `json:"username"`
	Password string `json:"password,omitempty"`
}

type UserDetails struct {
	ID       int    `json:"id"`
	Name     string `json:"name"`
	Age      int    `json:"age"`
	Height   int    `json:"height"`
	Weight   int    `json:"weight"`
	Gender   string `json:"gender"`
	ActivityLevel string `json:"activity_level"`
}

type Claims struct {
	ID int
	Username string
	jwt.RegisteredClaims
}

