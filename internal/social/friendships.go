package social

import (
	"gopherfit/internal/api"
	"net/http"
)

func (h *Handler) getUserFriends(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE user1_id = ? OR user2_id = ? AND status = 'accepted'`,
		userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch friendships", err)
		return
	}

	friendships := []Friendship{}
	for rows.Next() {
		var f Friendship
		rows.Scan(&f.User1ID, &f.User2ID, &f.ActionUserID, &f.Status)
		friendships = append(friendships, f)
	}
	rows.Close()

	api.WriteSuccess(w, http.StatusOK, friendships)
}

func (h *Handler) getUserPendingRequests(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE action_id = ? AND status = 'pending'`,
		userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch friendships", err)
		return
	}

	friendships := []Friendship{}
	for rows.Next() {
		var f Friendship
		rows.Scan(&f.User1ID, &f.User2ID, &f.ActionUserID, &f.Status)
		friendships = append(friendships, f)
	}
	rows.Close()

	api.WriteSuccess(w, http.StatusOK, friendships)
}

func (h *Handler) addFriendship(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	var friendship Friendship
	if !api.DecodeJSON(w, r, &friendship) {
		return
	}

	user1 := min(friendship.User1ID, friendship.User2ID)
	user2 := max(friendship.User1ID, friendship.User2ID)

	_, err := h.DB.Exec(`
		INSERT INTO friendships (user1_id, user2_id, action_user_id, status)
		VALUES (?, ?, ?)
	`, user1, user2, userID, friendship.Status)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert friendship", err)
		return
	}

	friendship.ActionUserID = userID
	friendship.User1ID = user1
	friendship.User2ID = user2
	api.WriteSuccess(w, http.StatusCreated, friendship)
}
