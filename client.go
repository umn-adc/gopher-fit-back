package main

import (
	"github.com/gorilla/websocket"
)

type Client struct {
	ID   int
	Conn *websocket.Conn
	Send chan []byte
}

func NewClient(conn *websocket.Conn, hub *Hub) *Client {
	return &Client{
		Conn: conn,
		Send: make(chan []byte),
	}
}

func (c *Client) readPump() {
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
