package social

type LeaderboardEntry struct {
	UserID      int     `json:"user_id"`
	Username    string  `json:"username"`
	Score       int     `json:"score"`   // Placeholder for whatever metric we chose
	Rank        int     `json:"rank"`
}