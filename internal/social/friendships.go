package social

import (
	"gopherfit/internal/api"
	"net/http"
)

// @Summary Get users accepted friends
// @Tags social
// @Security BearerAuth
// @Success 200 {array} Friendship
// @Router /social/friendships [get]
func (h *Handler) getFriends(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			user1_id = ? OR user2_id = ?
			AND status = 'accepted'`,
		userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch friends", err)
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

func (h *Handler) getOutgoingRequests(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			action_id = ?
			AND status = 'pending'`,
		userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch outgoing requests", err)
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

func (h *Handler) getIncomingRequests(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			NOT action_user_id = ?
			AND ? IN (user1_id, user2_id)
			AND status = 'pending'`,
		userID, userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch incoming requests", err)
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

func (h *Handler) getOutgoingBlocks(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			action_id = ?
			AND status = 'blocked'`,
		userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch outgoing blocks", err)
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

func (h *Handler) getIncomingBlocks(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE 
			NOT action_user_id = ? 
			AND ? IN (user1_id, user2_id) 
			AND status = 'blocked'`,
		userID, userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch incoming blocks", err)
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

func (h *Handler) getFriendship(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	user2ID, ok := api.PathInt(w, r, "user2_id")
	if !ok {
		return
	}

	user1 := min(userID, user2ID)
	user2 := max(userID, user2ID)

	var friendship Friendship
	err := h.DB.QueryRow(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			user1_id = ?
			AND user2_id = ?`,
		user1, user2).Scan(
		&friendship.User1ID, &friendship.User2ID, &friendship.ActionUserID, &friendship.Status)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch friendship", err)
		return
	}
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

	// Make sure the user is actually making themselves one of the friends
	if user1 != userID && user2 != userID {
		api.WriteError(w, http.StatusBadRequest, "invalid userIDs", nil)
		return
	}

	// Don't allow a friendship to start as accepted
	if friendship.Status == "accepted" {
		api.WriteError(w, http.StatusBadRequest, "Request cannot be instansiated to 'accepted'", nil)
		return
	}

	_, err := h.DB.Exec(`
		INSERT INTO friendships (user1_id, user2_id, action_user_id, status)
		VALUES (?, ?, ?, ?)
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

// So incredibly insecure
/*
Security Cases:
- User is trying to change their own pending request to accepted
- User is trying to change anything in another user's block
*/
func (h *Handler) updateFriendship(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	user2ID, ok := api.PathInt(w, r, "user2_id")
	if !ok {
		return
	}

	var friendship Friendship
	if !api.DecodeJSON(w, r, &friendship) {
		return
	}

	user1 := min(userID, user2ID)
	user2 := max(userID, user2ID)

	res, err := h.DB.Exec(`
		UPDATE friendships
		SET
			user1_id = ?,
			user2_id = ?,
			action_user_id = ?,
			status = ?
		WHERE
			user1_id = ?
			AND user2_id = ?`,
		friendship.User1ID, friendship.User2ID, friendship.ActionUserID, friendship.Status, user1, user2)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to update friendship", err)
		return
	}

	if !api.CheckAffected(w, res, "Friendship not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func (h *Handler) deleteFriendship(w http.ResponseWriter, r *http.Request) {}
