package api

import (
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
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
	decoder := json.NewDecoder(r.Body)
	if err := decoder.Decode(v); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return false
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		WriteError(w, http.StatusBadRequest, "Request body must contain one JSON value", err)
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

// PositivePathInt parses a positive resource ID, returning 400 otherwise.
func PositivePathInt(w http.ResponseWriter, r *http.Request, key string) (int, bool) {
	id, ok := PathInt(w, r, key)
	if !ok {
		return 0, false
	}
	if id <= 0 {
		WriteError(w, http.StatusBadRequest, "Invalid "+key, nil)
		return 0, false
	}
	return id, true
}

// CheckAffected checks that at least one row was affected by a DB exec.
// Writes 404 and returns false if zero rows were affected.
//
//	if !api.CheckAffected(w, res, "Workout not found") { return }
func CheckAffected(w http.ResponseWriter, res sql.Result, msg string) bool {
	n, err := res.RowsAffected()
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "Failed to verify database update", err)
		return false
	}
	if n == 0 {
		WriteError(w, http.StatusNotFound, msg, nil)
		return false
	}
	return true
}

// Rollback rolls a transaction back and logs unexpected rollback failures.
// It is intended for deferred cleanup after a transaction begins.
func Rollback(tx *sql.Tx) {
	if err := tx.Rollback(); err != nil && !errors.Is(err, sql.ErrTxDone) {
		log.Printf("ERROR rolling back transaction: %v", err)
	}
}

// IsUniqueViolation recognizes SQLite uniqueness errors without coupling
// handlers to driver-specific error types.
func IsUniqueViolation(err error) bool {
	return err != nil && strings.Contains(strings.ToLower(err.Error()), "unique constraint failed")
}

// IsCheckViolation recognizes SQLite CHECK constraint failures caused by
// invalid request values.
func IsCheckViolation(err error) bool {
	return err != nil && strings.Contains(strings.ToLower(err.Error()), "check constraint failed")
}
