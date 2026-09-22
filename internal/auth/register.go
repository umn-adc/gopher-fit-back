package auth

import (
	"encoding/json"
	"net/http"
	"unicode"

	"gopherfit/internal/api"

	"golang.org/x/crypto/bcrypt"
)

// @Summary Register new user
// @Tags auth
// @Param request body RegisterRequest true "Registration details"
// @Success 201 {object} AuthResponse
// @Router /auth/register [post]
func (h *Handler) handleRegister(w http.ResponseWriter, r *http.Request) {
	if h.Tokens == nil {
		api.WriteError(w, http.StatusInternalServerError, "Authentication is not configured", nil)
		return
	}

	var user User
	if !api.DecodeJSON(w, r, &user) {
		return
	}

	if !ValidUsername(user.Username) || !ValidPasswd(user.Password) {
		api.WriteError(w, http.StatusBadRequest, "Invalid credentials", nil)
		return
	}

	hashedPasswd, err := bcrypt.GenerateFromPassword([]byte(user.Password), bcrypt.DefaultCost)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to hash password", err)
		return
	}

	goalsJSON, err := json.Marshal(user.Goals)
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid goals", err)
		return
	}
	sportsJSON, err := json.Marshal(user.Sports)
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid sports", err)
		return
	}

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to begin registration", err)
		return
	}
	defer api.Rollback(tx)

	res, err := tx.Exec(`INSERT INTO users (username, password) VALUES (?, ?)`, user.Username, hashedPasswd)
	if err != nil {
		if api.IsUniqueViolation(err) {
			api.WriteError(w, http.StatusConflict, "Username already exists", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to create user", err)
		return
	}

	id, err := res.LastInsertId()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to get user ID", err)
		return
	}
	user.ID = int(id)

	_, err = tx.Exec(`INSERT INTO profiles (user_id, name, age, height, weight, gender, activity_level, goals, sports)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		user.ID, user.Name, user.Age, user.Height, user.Weight, user.Gender, user.ActivityLevel, string(goalsJSON), string(sportsJSON))
	if err != nil {
		if api.IsCheckViolation(err) {
			api.WriteError(w, http.StatusBadRequest, "Invalid profile", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to create profile", err)
		return
	}

	if err := tx.Commit(); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to commit registration", err)
		return
	}

	tokenString, err := h.Tokens.CreateToken(user)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to create token", err)
		return
	}

	api.WriteSuccess(w, http.StatusCreated, map[string]any{
		"token":    tokenString,
		"user_id":  user.ID,
		"username": user.Username,
	})
}

func ValidUsername(username string) bool {
	if username == "" {
		return false
	}
	return true
}

func ValidPasswd(passwd string) bool {
	if passwd == "" {
		return false
	}
	sevenOrMore, number, upper, special := verifyPassword(passwd)
	return sevenOrMore && number && upper && special
}

func verifyPassword(s string) (sevenOrMore, number, upper, special bool) {
	letters := 0
	for _, c := range s {
		switch {
		case unicode.IsNumber(c):
			number = true
		case unicode.IsUpper(c):
			upper = true
			letters++
		case unicode.IsPunct(c) || unicode.IsSymbol(c):
			special = true
		case unicode.IsLetter(c) || c == ' ':
			letters++
		default:
			return false, false, false, false
		}
	}
	sevenOrMore = letters >= 7
	return
}
