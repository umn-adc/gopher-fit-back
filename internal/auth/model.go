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
	ID            int      `json:"id"`
	Username      string   `json:"username"`
	Password      string   `json:"password,omitempty"`
	Name          string   `json:"name"`
	Age           int      `json:"age"`
	Height        int      `json:"height"`
	Weight        int      `json:"weight"`
	Gender        string   `json:"gender"`
	ActivityLevel string   `json:"activity_level"`
	Goals         []string `json:"goals"`
	Sports        []string `json:"sports"`
}

type LoginRequest struct {
	Username string `json:"username" example:"gopher"`
	Password string `json:"password" example:"MyP@ssw0rd!"`
}

type RegisterRequest struct {
	Username      string   `json:"username" example:"gopher"`
	Password      string   `json:"password" example:"MyP@ssw0rd!"`
	Name          string   `json:"name" example:"Mr. Fit"`
	Age           int      `json:"age" example:"25"`
	Height        int      `json:"height" example:"180"`
	Weight        int      `json:"weight" example:"75"`
	Gender        string   `json:"gender" example:"Male" enums:"Male,Female,Other"`
	ActivityLevel string   `json:"activity_level" example:"Moderately Active" enums:"Sedentary,Lightly Active,Moderately Active,Very Active,Extra Active"`
	Goals         []string `json:"goals" example:"Build Muscle,Lose Weight"`
	Sports        []string `json:"sports" example:"Basketball,Football"`
}

type AuthResponse struct {
	Token    string `json:"token" example:"eyJhbGciOiJIUzI1NiIs..."`
	UserID   int    `json:"UserID" example:"1"`
	Username string `json:"username" example:"johndoe"`
}

type Claims struct {
	ID       int
	Username string
	jwt.RegisteredClaims
}

