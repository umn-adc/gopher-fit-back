package messaging

import (
	"gopherfit/internal/api"
	"net/http"
)

func (h *Handler) getUserChats(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(`
		SELECT c.id, c.chat_name
		FROM chats m
		WHERE c.user_id = ?
		GROUP BY c.id`, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch meals", err)
		return
	}

	chats := []Chat{}
	for rows.Next() {
		var c Chat
		rows.Scan(&c.ID, &c.ChatName)
		chats = append(chats, c)
	}

	api.WriteSuccess(w, http.StatusOK, chats)
}
