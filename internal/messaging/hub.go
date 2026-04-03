package messaging

import (
	"gopherfit/internal/api"
	"net/http"

	"github.com/gorilla/websocket"
)

type Client struct {
	ID   int
	Conn *websocket.Conn
	Send chan []byte
}

type Conversation struct {
	ID    int
	Users map[int]bool
}

type Hub struct {
	Clients       map[int]*Client
	Conversations map[int]*Conversation
	Register      chan *Client
	Unregister    chan *Client
	Broadcast     chan *Message
}

func NewHub() *Hub {
	return &Hub{
		Clients:       make(map[int]*Client),
		Conversations: make(map[int]*Conversation),
		Register:      make(chan *Client),
		Unregister:    make(chan *Client),
		Broadcast:     make(chan *Message),
	}
}

func (h *Hub) run() {
	for {
		select {
		case client := <-h.Register:
			h.Clients[client.ID] = client
		case client := <-h.Unregister:
			_, ok := h.Clients[client.ID]
			if ok {
				delete(h.Clients, client.ID)
				close(client.Send)
			}
		case msg := <-h.Broadcast:
			// convo := h.Conversations[msg.ChatID]
		}

	}
}

func (m *Hub) serveWS(w http.ResponseWriter, r *http.Request) {
	println("New Connection")

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to set up websocket", err)
		return
	}
	client := NewClient(conn, m)

	m.addClient(client)

	// Start client processes
	go client.readMessages()
	go client.writeMessages()
}
