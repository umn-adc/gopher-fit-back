package social

// LeaderboardEntry represents a user's position on the leaderboard
type LeaderboardEntry struct {
	UserID   int    `json:"user_id" example:"1"`
	Username string `json:"username" example:"alice"`
	Score    int    `json:"score" example:"250"`
	Rank     int    `json:"rank" example:"1"`
}

type Friendship struct {
	User1ID      int    `json:"user1_id" example:"1"`
	User2ID      int    `json:"user2_id" example:"2"`
	ActionUserID int    `json:"action_user_id" example:"1"`
	Status       string `json:"status" example:"pending"`
}
