package main

import (
	"gopherfit/internal/api"
	"net/http"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

type Manager struct {
}

func NewManager() *Manager {
	return &Manager{}
}

func (m *Manager) serveWS(w http.ResponseWriter, r *http.Request) {
	println("New Connection")

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to set up websocket", err)
		return
	}

	conn.Close()
}
