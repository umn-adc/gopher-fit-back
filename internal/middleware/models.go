package middleware

import (

)

type contextKey string

const (
	CtxUserIDKey contextKey = "userID"
	CtxUsernameKey contextKey = "username"
)
