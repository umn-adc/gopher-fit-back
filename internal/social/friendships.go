package social

import (
	"database/sql"
	"fmt"
	"net/http"

	"gopherfit/internal/api"
)

func scanFriendships(rows *sql.Rows) ([]Friendship, error) {
	defer rows.Close()

	friendships := []Friendship{}
	for rows.Next() {
		var friendship Friendship
		if err := rows.Scan(&friendship.User1ID, &friendship.User2ID, &friendship.ActionUserID, &friendship.Status); err != nil {
			return nil, fmt.Errorf("scan friendship: %w", err)
		}
		friendships = append(friendships, friendship)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate friendships: %w", err)
	}
	return friendships, nil
}

// @Summary Get users relationships
// @Tags social
// @Security BearerAuth
// @Success 200 {array} Friendship
// @Router /social/friendships [get]
func (h *Handler) getFriendships(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			user1_id = ? OR user2_id = ?`,
		userID, userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch relationships", err)
		return
	}

	friendships, err := scanFriendships(rows)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to read relationships", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, friendships)
}

// @Summary Get users accepted friends
// @Tags social
// @Security BearerAuth
// @Success 200 {array} Friendship
// @Router /social/friendships/accepted [get]
func (h *Handler) getAccepted(w http.ResponseWriter, r *http.Request) {
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

	friendships, err := scanFriendships(rows)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to read friends", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, friendships)
}

// @Summary Get users outgoing friend requests
// @Tags social
// @Security BearerAuth
// @Success 200 {array} Friendship
// @Router /social/friendships/outpending [get]
func (h *Handler) getOutgoingRequests(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			action_user_id = ?
			AND status = 'pending'`,
		userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch outgoing requests", err)
		return
	}

	friendships, err := scanFriendships(rows)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to read outgoing requests", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, friendships)
}

// @Summary Get users incoming friend requests
// @Tags social
// @Security BearerAuth
// @Success 200 {array} Friendship
// @Router /social/friendships/inpending [get]
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

	friendships, err := scanFriendships(rows)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to read incoming requests", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, friendships)
}

// @Summary Get users outgoing blocks
// @Tags social
// @Security BearerAuth
// @Success 200 {array} Friendship
// @Router /social/friendships/outblocks [get]
func (h *Handler) getOutgoingBlocks(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(
		`SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE
			action_user_id = ?
			AND status = 'blocked'`,
		userID)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch outgoing blocks", err)
		return
	}

	friendships, err := scanFriendships(rows)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to read outgoing blocks", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, friendships)
}

// @Summary Get users incoming blocks
// @Tags social
// @Security BearerAuth
// @Success 200 {array} Friendship
// @Router /social/friendships/inblocks [get]
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

	friendships, err := scanFriendships(rows)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to read incoming blocks", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, friendships)
}

// @Summary Get relationship by friend's id
// @Tags social
// @Security BearerAuth
// @Param user2_id path int true "friend's id"
// @Success 200 {array} Friendship
// @Router /social/friendships/{user2_id} [get]
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
		if err == sql.ErrNoRows {
			api.WriteError(w, http.StatusNotFound, "Friendship not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch friendship", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, friendship)
}

// @Summary Create a relationship
// @Tags social
// @Security BearerAuth
// @Param request body Friendship true "Friendship data"
// @Success 201 {object} Friendship
// @Router /social/friendships [post]
func (h *Handler) addFriendship(w http.ResponseWriter, r *http.Request) {
	/*
		OK Cases:
		- outgoing pending
		- outgoing block
		Security Cases:
		- outgoing accepted
	*/
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
		api.WriteError(w, http.StatusBadRequest, "Friendship cannot start as 'accepted'", nil)
		return
	}

	_, err := h.DB.Exec(`
		INSERT INTO friendships (user1_id, user2_id, action_user_id, status)
		VALUES (?, ?, ?, ?)
	`, user1, user2, userID, friendship.Status)

	if err != nil {
		if api.IsUniqueViolation(err) {
			api.WriteError(w, http.StatusConflict, "Friendship already exists", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "failed to insert friendship", err)
		return
	}

	friendship.ActionUserID = userID
	friendship.User1ID = user1
	friendship.User2ID = user2
	api.WriteSuccess(w, http.StatusCreated, friendship)
}

// @Summary Update Friendship
// @Tags social
// @Security BearerAuth
// @Param user2_id path int true "Friend ID"
// @Param request body Friendship true "Friendship data"
// @Success 200 {object} Friendship
// @Router /social/friendships/{user2_id} [put]
func (h *Handler) updateFriendship(w http.ResponseWriter, r *http.Request) {
	/*
		OK Cases:
		- Incoming accepted to block
		- Outgoing accepted to block
		- Incoming pending to block
		- Outgoing pending to block
		- Incoming pending to accepted
		Unsure Cases (Feel weird but do not cause security issues):
		- Incoming accepted to pending
		- Outgoing accepted to pending
		- Outgoing block to pending
		Security Cases:
		- Outgoing pending to accepted
		- Incoming block to pending
		- Incoming block to accepted
		- Incoming block to block
		- Outgoing block to accepted
		- Changing anything to itself (e.g. Incoming/Outgoing pending to pending)
		- Changing any userIDs (Only status should be allowed to change)
	*/

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

	var og Friendship
	err := h.DB.QueryRow(`
		SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE user1_id = ? AND user2_id = ?`,
		user1, user2).Scan(
		&og.User1ID, &og.User2ID, &og.ActionUserID, &og.Status)
	if err != nil {
		if err == sql.ErrNoRows {
			api.WriteError(w, http.StatusNotFound, "Friendship not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch friendship", err)
		return
	}

	//Security Cases
	// Changing users
	new_user1 := min(friendship.User1ID, friendship.User2ID)
	new_user2 := max(friendship.User1ID, friendship.User2ID)
	if user1 != new_user1 || user2 != new_user2 {
		api.WriteError(w, http.StatusBadRequest, "Cannot change friend ids", nil)
		return
	}

	//Not changing status
	if friendship.Status == og.Status {
		api.WriteError(w, http.StatusBadRequest, "Status must be changed on update", nil)
		return
	}

	//Can't change incoming block
	if og.Status == "blocked" && og.ActionUserID != userID {
		api.WriteError(w, http.StatusBadRequest, "Cannot change users incoming block", nil)
		return
	}

	// Only incoming pending can become accepted
	if friendship.Status == "accepted" {
		if og.Status == "pending" {
			if og.ActionUserID == userID {
				api.WriteError(w, http.StatusBadRequest, "Cannot accept an outgoing pending request", nil)
				return
			}
		} else {
			api.WriteError(w, http.StatusBadRequest, "Cannot accept a non-pending request", nil)
			return
		}
	}

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
		user1, user2, userID, friendship.Status, user1, user2)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to update friendship", err)
		return
	}

	if !api.CheckAffected(w, res, "Friendship not found") {
		return
	}

	friendship.ActionUserID = userID
	friendship.User1ID = user1
	friendship.User2ID = user2
	api.WriteSuccess(w, http.StatusOK, friendship)
}

// @Summary Delete friendship
// @Tags social
// @Security BearerAuth
// @Param user2_id path int true "Friend ID"
// @Success 204 "No Content"
// @Router /social/friendships/{user2_id} [delete]
func (h *Handler) deleteFriendship(w http.ResponseWriter, r *http.Request) {
	/*
		Much more straightforward. Just can't delete an incoming block
		OK Cases:
		- Deleting incoming accepted
		- Deleting outgoing accepted
		- Deleting incoming pending
		- Deleting outgoing pending
		- Deleting outgoing block
		Security Cases:
		- Deleting incoming block
	*/
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

	var og Friendship
	err := h.DB.QueryRow(`
		SELECT user1_id, user2_id, action_user_id, status
		FROM friendships
		WHERE user1_id = ? AND user2_id = ?`,
		user1, user2).Scan(
		&og.User1ID, &og.User2ID, &og.ActionUserID, &og.Status)

	if err != nil {
		if err == sql.ErrNoRows {
			api.WriteError(w, http.StatusNotFound, "Friendship not found", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch friendship", err)
		return
	}

	//Check security case
	if og.Status == "blocked" && og.ActionUserID != userID {
		api.WriteError(w, http.StatusBadRequest, "Cannot delete another user's block", nil)
		return
	}

	res, err := h.DB.Exec(`
	DELETE FROM friendships
	WHERE user1_id = ? AND user2_id = ?`,
		user1, user2)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete friendship", err)
		return
	}

	if !api.CheckAffected(w, res, "Friendship not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
