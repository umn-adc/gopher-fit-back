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

type User struct {
	ID       int    `json:"id"`
	Username string `json:"username"`
	Password string `json:"password,omitempty"`
}