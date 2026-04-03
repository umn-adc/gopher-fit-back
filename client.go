package main

import (
	"github.com/gorilla/websocket"
)

type Client struct {
	connection *websocket.Conn
	hub        *Hub

	//egress is used to avoid concurrent writes on the connection
	egress chan []byte
}

func NewClient(conn *websocket.Conn, hub *Hub) *Client {
	return &Client{
		connection: conn,
		hub:        hub,
		egress:     make(chan []byte),
	}
}

func (c *Client) readMessages() {
	defer func() {
		//cleanup connection
		c.hub.removeClient(c)
	}()
	for {
		messageType, payload, err := c.connection.ReadMessage()

		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				println("Error")
			}
			break
		}
	}
}

func (c *Client) writeMessages() {
	defer func() {
		c.hub.removeClient(c)
	}()
	for {
		select {
		case message, ok := <-c.egress:
			if !ok {
				if err := c.connection.WriteMessage(websocket.CloseMessage, nil); err != nil {
					println("error", err)
				}
				return
			}
			err := c.connection.WriteMessage(websocket.TextMessage, message)
			if err != nil {
				println("Error", err)

			}
			println("Message sent")
		}
	}
}
