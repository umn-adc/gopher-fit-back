package api

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"
)

type contextKey string

const CtxUserIDKey contextKey = "userID"

// GetUserID extracts the user ID from the JWT context.
// Writes 401 and returns false if not present.
//
//	userID, ok := api.GetUserID(w, r)
//	if !ok { return }
func GetUserID(w http.ResponseWriter, r *http.Request) (int, bool) {
	userID, ok := r.Context().Value(CtxUserIDKey).(int)
	if !ok {
		WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
	}
	return userID, ok
}

// DecodeJSON decodes the request body into v.
// Writes 400 and returns false on failure.
//
//	if !api.DecodeJSON(w, r, &workout) { return }
func DecodeJSON(w http.ResponseWriter, r *http.Request, v any) bool {
	if err := json.NewDecoder(r.Body).Decode(v); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return false
	}
	return true
}

// PathInt reads a path parameter and parses it as an int.
// Writes 400 and returns false on failure.
//
//	id, ok := api.PathInt(w, r, "id")
//	if !ok { return }
func PathInt(w http.ResponseWriter, r *http.Request, key string) (int, bool) {
	v, err := strconv.Atoi(r.PathValue(key))
	if err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid "+key, err)
		return 0, false
	}
	return v, true
}

// CheckAffected checks that at least one row was affected by a DB exec.
// Writes 404 and returns false if zero rows were affected.
//
//	if !api.CheckAffected(w, res, "Workout not found") { return }
func CheckAffected(w http.ResponseWriter, res sql.Result, msg string) bool {
	n, err := res.RowsAffected()
	if err != nil || n == 0 {
		WriteError(w, http.StatusNotFound, msg, nil)
		return false
	}
	return true
}

