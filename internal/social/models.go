package social

// LeaderboardEntry represents a user's position on the leaderboard
type LeaderboardEntry struct {
	UserID   int    `json:"user_id" example:"1"`
	Username string `json:"username" example:"alice"`
	Score    int    `json:"score" example:"250"`
	Rank     int    `json:"rank" example:"1"`
}
