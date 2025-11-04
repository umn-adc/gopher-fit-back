package auth

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

var secretKey = []byte("secretkey") // TODO: Change this to use env var

/*
* Creates JWT token based off of user
* @param u User, our user
* @return tokenString string, our token string which may be empty if error occurs
* @return error, nil if no error occurs
*/
func createToken(u User) (string, error) {
	// Create a claim
	claims := &Claims{
		ID: u.ID,
		Username: u.Username,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour * 24)),
		},
	}

	// Generate token
    token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)

	// Sign using our secret key
	tokenString, err := token.SignedString(secretKey)
	if err != nil {
		return "", err
	}
	return tokenString, nil
}

/*
* Verifies our token
* @param tokenString string, our token
* @return userID int, -1 if error occurred otherwise our user's ID
* @return username string, our username
* @return error, nil if no error
*/
func verifyToken(tokenString string) (int, string, error) {
	claims := &Claims{}
	token, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (interface{}, error) {
		return secretKey, nil
	})
	if err != nil {
		return -1, "Error", err
	}
	if !token.Valid {
		return -1, "", fmt.Errorf("invalid token")
	}
	return claims.ID, claims.Username, nil
}

