package social

import "net/http"
// import "encoding/json"

func Register(mux *http.ServeMux) {
	mux.HandleFunc("/social/leaderboard", leaderboardHandler)
}

func leaderboardHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// call computeLeaderboard()

	// encode data to json and return
	return
}
