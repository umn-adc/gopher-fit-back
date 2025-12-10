package user

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
)

type UserResponse struct {
	Username string `json:"username"`
}

func getUsernameByUserID(userID int) (string, error) {
	mockUsers := map[int]string{
		1: "john_doe",
		2: "jane_smith",
		3: "alex_123",
	}

	username, exists := mockUsers[userID]
	if !exists {
		return "", errors.New("user not found")
	}

	return username, nil
}

func handlergetUser(w http.ResponseWriter, r *http.Request) {
	userIDStr := r.URL.Query().Get("id")

	userID, err := strconv.Atoi(userIDStr)
	if err != nil {
		http.Error(w, "Invalid user ID", http.StatusBadRequest)
		return
	}

	username, err := getUsernameByUserID(userID)
	if err != nil {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	response := UserResponse{
		Username: username,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
	// w.WriteHeader(200)
}
