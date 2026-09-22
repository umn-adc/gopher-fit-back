package social

import (
	"net/http"

	"gopherfit/internal/api"
	"gopherfit/internal/records"
)

// @Summary Get a per-exercise leaderboard
// @Description Ranks each participant's highest positive weight using descending dense rank. Percentile is 100 times participants at or below the weight divided by all participants of the exercise. Ties share rank and percentile. Names are matched ignoring case and collapsed whitespace. Unknown exercises return an empty array. This replaces the static score leaderboard.
// @Tags social
// @Security BearerAuth
// @Produce json
// @Param exercise query string true "Exercise name" example(Bench Press)
// @Success 200 {array} LeaderboardEntry
// @Failure 400 {object} api.ErrorResponse "Exercise is required"
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /social/leaderboard [get]
func (h *Handler) getLeaderboard(w http.ResponseWriter, r *http.Request) {
	if _, ok := api.GetUserID(w, r); !ok {
		return
	}
	exercise := records.ExerciseKey(r.URL.Query().Get("exercise"))
	if exercise == "" {
		api.WriteError(w, http.StatusBadRequest, "Exercise is required", nil)
		return
	}

	rows, err := h.DB.QueryContext(r.Context(), `
		SELECT pr.user_id, u.username, pr.max_weight,
			DENSE_RANK() OVER (ORDER BY pr.max_weight DESC),
			100.0 * CUME_DIST() OVER (ORDER BY pr.max_weight ASC)
		FROM personal_records pr JOIN users u ON u.id = pr.user_id
		WHERE pr.exercise_key = ?
		ORDER BY pr.max_weight DESC, pr.user_id ASC`, exercise)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch leaderboard", err)
		return
	}

	defer rows.Close()
	entries := []LeaderboardEntry{}
	for rows.Next() {
		var entry LeaderboardEntry
		if err := rows.Scan(&entry.UserID, &entry.Username, &entry.MaxWeight, &entry.Rank, &entry.Percentile); err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Failed to read leaderboard", err)
			return
		}
		entries = append(entries, entry)
	}
	if err := rows.Err(); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to iterate leaderboard", err)
		return
	}
	api.WriteSuccess(w, http.StatusOK, entries)
}

// @Summary Get the caller's personal exercise records and ranks
// @Description Returns only the caller's positive-weight records, ordered by normalized exercise name. Rank and percentile are calculated across all participants of each exercise before filtering to the caller. Percentile counts users at or below the record; ties share descending dense rank. Empty results are an array.
// @Tags social
// @Security BearerAuth
// @Produce json
// @Success 200 {array} MuscleRank
// @Failure 401 {object} api.ErrorResponse
// @Failure 500 {object} api.ErrorResponse
// @Router /social/muscle-ranks [get]
func (h *Handler) getMuscleRanks(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}
	rows, err := h.DB.QueryContext(r.Context(), `
		WITH ranked AS (
			SELECT user_id, exercise_key, exercise_name, max_weight, source_workout_item_id,
				DENSE_RANK() OVER (PARTITION BY exercise_key ORDER BY max_weight DESC) AS rank,
				100.0 * CUME_DIST() OVER (PARTITION BY exercise_key ORDER BY max_weight ASC) AS percentile
			FROM personal_records
		)
		SELECT user_id, exercise_key, exercise_name, max_weight, source_workout_item_id, rank, percentile
		FROM ranked WHERE user_id = ? ORDER BY exercise_key`, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch personal records", err)
		return
	}
	defer rows.Close()
	ranks := []MuscleRank{}
	for rows.Next() {
		var rank MuscleRank
		if err := rows.Scan(&rank.UserID, &rank.ExerciseKey, &rank.ExerciseName, &rank.MaxWeight, &rank.SourceWorkoutItemID, &rank.Rank, &rank.Percentile); err != nil {
			api.WriteError(w, http.StatusInternalServerError, "Failed to read personal record", err)
			return
		}
		ranks = append(ranks, rank)
	}
	if err := rows.Err(); err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to iterate personal records", err)
		return
	}
	api.WriteSuccess(w, http.StatusOK, ranks)
}
