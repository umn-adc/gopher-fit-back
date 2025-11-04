package nutrition

import (
	"net/http"
)

// TODO
// ADD JWT AUTHORIZATION

func (h *Handler) getGoals(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		http.Error(w, "user_id required", http.StatusBadRequest)
		return
	}

	rows, err := h.DB.Query("SELECT * FROM meals WHERE user_id = ?", userID)
	if err != nil {
		http.Error(w, "failed to fetch goals", http.StatusInternalServerError)
		return
	}
	defer rows.Close()
}