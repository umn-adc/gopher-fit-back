package social

import (
	"database/sql"
	"net/http"
)

type Handler struct {
	DB *sql.DB
}

func NewHandler(db *sql.DB) *Handler {
	return &Handler{DB: db}
}

func (h *Handler) RegisterRoutes() *http.ServeMux {
	r := http.NewServeMux()

	//Leaderboard CRUD
	r.HandleFunc("GET /social/leaderboard", h.getLeaderboard)

	//Friend CRUD
	r.HandleFunc("GET /social/friendships", h.getFriendships)
	r.HandleFunc("POST /social/friendships", h.addFriendship)
	r.HandleFunc("GET /social/friendships/{user2_id}", h.getFriendship)
	r.HandleFunc("PUT /social/friendships/{user2_id}", h.updateFriendship)
	r.HandleFunc("DELETE /social/friendships/{user2_id}", h.deleteFriendship)
	r.HandleFunc("GET /social/friendships/accepted", h.getAccepted)
	r.HandleFunc("GET /social/friendships/outpending", h.getOutgoingRequests)
	r.HandleFunc("GET /social/friendships/inpending", h.getIncomingRequests)
	r.HandleFunc("GET /social/friendships/outblocks", h.getOutgoingBlocks)
	r.HandleFunc("GET /social/friendships/inblocks", h.getIncomingBlocks)

	return r
}
