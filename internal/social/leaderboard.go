package social

import (
	"net/http"

	"gopherfit/internal/api"
)

// @Summary Get leaderboard
// @Tags social
// @Success 200 {array} LeaderboardEntry
// @Router /social/leaderboard [get]
func (h *Handler) getLeaderboard(w http.ResponseWriter, r *http.Request) {
	leaderboard, err := h.computeLeaderboard()
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch leaderboard", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, leaderboard)
}

func (h *Handler) computeLeaderboard() ([]LeaderboardEntry, error) {
	// TODO: Implement with real DB queries
	testData := []LeaderboardEntry{
		{UserID: 1, Username: "alice", Score: 250, Rank: 1},
		{UserID: 2, Username: "bob", Score: 200, Rank: 2},
		{UserID: 3, Username: "charlie", Score: 150, Rank: 3},
		{UserID: 4, Username: "diana", Score: 120, Rank: 4},
		{UserID: 5, Username: "evan", Score: 100, Rank: 5},
	}

	return testData, nil
}
