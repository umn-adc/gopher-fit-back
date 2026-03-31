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
	var user User
	if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid JSON", err)
		return
	}

	if !validUsername(user.Username) || !validPasswd(user.Password) {
		api.WriteError(w, http.StatusBadRequest, "Invalid credentials", nil)
		return
	}

	hashedPasswd, err := bcrypt.GenerateFromPassword([]byte(user.Password), bcrypt.DefaultCost)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to hash password", err)
		return
	}

	res, err := h.DB.Exec(`INSERT INTO users (username, password) VALUES (?, ?)`, user.Username, hashedPasswd)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to create user", err)
		return
	}

	id, err := res.LastInsertId()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to get user ID", err)
		return
	}
	user.ID = int(id)

	goalsJSON, _ := json.Marshal(user.Goals)
	sportsJSON, _ := json.Marshal(user.Sports)

	_, err = h.DB.Exec(`INSERT INTO profiles (user_id, name, age, height, weight, gender, activity_level, goals, sports)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		user.ID, user.Name, user.Age, user.Height, user.Weight, user.Gender, user.ActivityLevel, string(goalsJSON), string(sportsJSON))
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to create profile", err)
		return
	}

	tokenString, err := createToken(user)
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
