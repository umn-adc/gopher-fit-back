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
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
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
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
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
			(user1_id = ? OR user2_id = ?)
			AND status = 'accepted'`,
		userID, userID)

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
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
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
			AND ? IN (user1_id, user2_id)
			AND status = 'pending'`,
		userID, userID)

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
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
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
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
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
			AND ? IN (user1_id, user2_id)
			AND status = 'blocked'`,
		userID, userID)

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
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
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
// @Success 200 {object} Friendship
// @Failure 400 {object} api.ErrorResponse "Invalid or self user ID"
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /social/friendships/{user2_id} [get]
func (h *Handler) getFriendship(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	user1, user2, ok := friendshipPair(w, r, userID)
	if !ok {
		return
	}

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
// @Description Both user IDs must exist and include the caller. Only pending or blocked may be created. action_user_id is always set to the caller; a supplied value is ignored.
// @Tags social
// @Security BearerAuth
// @Accept json
// @Produce json
// @Param request body Friendship true "Friendship data"
// @Success 201 {object} Friendship
// @Failure 400 {object} api.ErrorResponse "Invalid IDs, status, or JSON"
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse "User not found"
// @Failure 409 {object} api.ErrorResponse "Relationship already exists"
// @Failure 500 {object} api.ErrorResponse
// @Router /social/friendships [post]
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
	if user1 <= 0 || user1 == user2 || (user1 != userID && user2 != userID) {
		api.WriteError(w, http.StatusBadRequest, "IDs must be distinct, positive, and include the caller", nil)
		return
	}

	// Don't allow a friendship to start as accepted
	if friendship.Status != "pending" && friendship.Status != "blocked" {
		api.WriteError(w, http.StatusBadRequest, "New relationships must be pending or blocked", nil)
		return
	}

	res, err := h.DB.ExecContext(r.Context(), `
		INSERT INTO friendships (user1_id, user2_id, action_user_id, status)
		SELECT ?, ?, ?, ?
		WHERE EXISTS (SELECT 1 FROM users WHERE id = ?)
		AND EXISTS (SELECT 1 FROM users WHERE id = ?)
	`, user1, user2, userID, friendship.Status, user1, user2)

	if err != nil {
		if api.IsUniqueViolation(err) {
			api.WriteError(w, http.StatusConflict, "Friendship already exists", nil)
			return
		}
		api.WriteError(w, http.StatusInternalServerError, "failed to insert friendship", err)
		return
	}
	if !api.CheckAffected(w, res, "User not found") {
		return
	}

	friendship.ActionUserID = userID
	friendship.User1ID = user1
	friendship.User2ID = user2
	api.WriteSuccess(w, http.StatusCreated, friendship)
}

// @Summary Update Friendship
// @Description Only the recipient may accept a pending request. Either participant may block unless already blocked by the other user. A block's owner may change it to pending; accepted relationships may return to pending. Same-status changes are rejected. IDs must match the existing pair; action_user_id is set to the caller.
// @Tags social
// @Security BearerAuth
// @Accept json
// @Produce json
// @Param user2_id path int true "Friend ID"
// @Param request body Friendship true "Friendship data"
// @Success 200 {object} Friendship
// @Failure 400 {object} api.ErrorResponse "Invalid IDs, status, JSON, or forbidden transition"
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse "Relationship not found"
// @Failure 409 {object} api.ErrorResponse "Relationship changed concurrently; reload before retrying"
// @Failure 500 {object} api.ErrorResponse
// @Router /social/friendships/{user2_id} [put]
func (h *Handler) updateFriendship(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	user1, user2, ok := friendshipPair(w, r, userID)
	if !ok {
		return
	}

	var friendship Friendship
	if !api.DecodeJSON(w, r, &friendship) {
		return
	}

	if friendship.Status != "pending" && friendship.Status != "accepted" && friendship.Status != "blocked" {
		api.WriteError(w, http.StatusBadRequest, "Invalid friendship status", nil)
		return
	}
	if min(friendship.User1ID, friendship.User2ID) != user1 || max(friendship.User1ID, friendship.User2ID) != user2 {
		api.WriteError(w, http.StatusBadRequest, "Cannot change friend ids", nil)
		return
	}

	var og Friendship
	err := h.DB.QueryRowContext(r.Context(), `
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

	// Match the state we authorized so a concurrent block cannot be overwritten.
	res, err := h.DB.ExecContext(r.Context(), `
		UPDATE friendships
		SET
			action_user_id = ?,
			status = ?
		WHERE
			user1_id = ?
			AND user2_id = ?
			AND action_user_id = ? AND status = ?`,
		userID, friendship.Status, user1, user2, og.ActionUserID, og.Status)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to update friendship", err)
		return
	}

	if !checkFriendshipMutation(w, res) {
		return
	}

	friendship.ActionUserID = userID
	friendship.User1ID = user1
	friendship.User2ID = user2
	api.WriteSuccess(w, http.StatusOK, friendship)
}

// @Summary Delete friendship
// @Description Either participant may delete pending or accepted relationships. Only the user who created a block may delete it. An incoming block cannot be removed by the blocked user.
// @Tags social
// @Security BearerAuth
// @Param user2_id path int true "Friend ID"
// @Success 204 "No Content"
// @Failure 400 {object} api.ErrorResponse "Invalid ID or cannot delete another user's block"
// @Failure 401 {object} api.ErrorResponse
// @Failure 404 {object} api.ErrorResponse "Relationship not found"
// @Failure 409 {object} api.ErrorResponse "Relationship changed concurrently; reload before retrying"
// @Failure 500 {object} api.ErrorResponse
// @Router /social/friendships/{user2_id} [delete]
func (h *Handler) deleteFriendship(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	user1, user2, ok := friendshipPair(w, r, userID)
	if !ok {
		return
	}

	var og Friendship
	err := h.DB.QueryRowContext(r.Context(), `
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

	res, err := h.DB.ExecContext(r.Context(), `
	DELETE FROM friendships
	WHERE user1_id = ? AND user2_id = ? AND action_user_id = ? AND status = ?`,
		user1, user2, og.ActionUserID, og.Status)

	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete friendship", err)
		return
	}

	if !checkFriendshipMutation(w, res) {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func friendshipPair(w http.ResponseWriter, r *http.Request, userID int) (int, int, bool) {
	otherID, ok := api.PositivePathInt(w, r, "user2_id")
	if !ok {
		return 0, 0, false
	}
	if otherID == userID {
		api.WriteError(w, http.StatusBadRequest, "A relationship requires two distinct users", nil)
		return 0, 0, false
	}
	return min(userID, otherID), max(userID, otherID), true
}

func checkFriendshipMutation(w http.ResponseWriter, res sql.Result) bool {
	count, err := res.RowsAffected()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to verify relationship update", err)
		return false
	}
	if count == 0 {
		api.WriteError(w, http.StatusConflict, "Relationship changed; reload before retrying", nil)
		return false
	}
	return true
}
