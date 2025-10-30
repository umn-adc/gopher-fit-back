package social

// Re-calculates the leaderboard from the DB every time a user sends a GET request
// Not scalable, but works for now
func computeLeaderboard() ([]LeaderboardEntry, error) {

	testData := []LeaderboardEntry{
		{UserID: 1, Username: "alice", Score: 250, Rank: 1},
		{UserID: 2, Username: "bob", Score: 200, Rank: 2},
		{UserID: 3, Username: "charlie", Score: 150, Rank: 3},
		{UserID: 4, Username: "diana", Score: 120, Rank: 4},
		{UserID: 5, Username: "evan", Score: 100, Rank: 5},
	}

	return testData, nil
}
