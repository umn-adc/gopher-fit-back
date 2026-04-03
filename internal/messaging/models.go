package messaging

type Chat struct {
	ID       int    `json:"id" example:"1"`
	ChatName string `json:"chat_name" example:"group1"`
}

type ChatMember struct {
	UserID int `json:"user_id" example:"1"`
	ChatID int `json:"chat_id" example:"1"`
}

type Message struct {
	ChatID int    `json:"chat_id" example:"1"`
	Body   string `json:"body" example:"hello"`
}
