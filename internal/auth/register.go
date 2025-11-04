package auth

import (
	"net/http"
	"unicode"
	"encoding/json"

	"golang.org/x/crypto/bcrypt"
)

// handleRegister handles POST /api/auth/register requests.
// Creates a user in database after receiving a unique username
func (h *Handler) handleRegister(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	passwd := r.URL.Query().Get("password")

	if !validUsername(username) || !validPasswd(passwd) {
		http.Error(w, "Invalid Credentials", http.StatusUnauthorized)
		return
	}

	// Hashes and salts password
	hashedPasswd, err := bcrypt.GenerateFromPassword([]byte(passwd), bcrypt.DefaultCost)
	if err != nil {
		http.Error(w, "Issue with User Signup", http.StatusInternalServerError)
		return
	}

	DB := h.DB
	res, err := DB.Exec(`INSERT INTO users (username, password)
				VALUES (?, ?)
	`, username, hashedPasswd)

	// Error with insertion
	if err != nil {
		http.Error(w, "Issue with User Signup", http.StatusInternalServerError)
		return
	}

	var user User
	id, err := res.LastInsertId()
	if err != nil {
		http.Error(w, "Issue with retrieving user ID", http.StatusInternalServerError)
	}

	user.ID = int(id)
	user.Username = username
	user.Password = passwd

	// Create jwt based off of the user
	tokenString, err := createToken(user)
	if err != nil {
		http.Error(w, "Issue with creating JWT token", http.StatusInternalServerError)
	}

	// Create our response and send as JSON
	response := struct {
		Token string `json:"token"`
		UserID  int
		Username string `json:"username"`
	}{
		Token: tokenString,
		UserID: user.ID,
		Username: user.Username,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

/*
* Checks username to see if it is a valid username
* @param username string, our username
* @return true if valid, else false
*/
func validUsername(username string) bool {
	if username == "" {
		return false
	}
	// TODO: Validate username

	return true
}

/*
* Validates password by ensuring a mix of characters
* @param passwd string, our password
* @return true if valid else false
*/
func validPasswd(passwd string) bool {
	if passwd == "" {
		return false
	}
	sevenOrMore, number, upper, special := verifyPassword(passwd)
	if !sevenOrMore || !number || !upper || !special {
		return false
	}
	return true
}

/*
* Checks if password has at least 7 letters, 1 number, 1 uppercase letter, and 1 special character
* @param s string, our password
* @return (sevenOrMore, number, upper, special) bool, true if it matches else false
*/
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
