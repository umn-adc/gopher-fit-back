package social

// LeaderboardEntry represents one user's best lift for the requested exercise.
type LeaderboardEntry struct {
	UserID     int     `json:"user_id" example:"1"`
	Username   string  `json:"username" example:"gopher"`
	MaxWeight  float64 `json:"max_weight" example:"135.5"`
	Rank       int     `json:"rank" example:"1"`
	Percentile float64 `json:"percentile" example:"100"`
}

// MuscleRank is the caller's record and standing among users of that exercise.
type MuscleRank struct {
	UserID              int     `json:"user_id" example:"1"`
	ExerciseKey         string  `json:"exercise_key" example:"bench press"`
	ExerciseName        string  `json:"exercise_name" example:"Bench Press"`
	MaxWeight           float64 `json:"max_weight" example:"135.5"`
	SourceWorkoutItemID int     `json:"source_workout_item_id" example:"12"`
	Rank                int     `json:"rank" example:"1"`
	Percentile          float64 `json:"percentile" example:"100"`
}

type Friendship struct {
	User1ID      int    `json:"user1_id" example:"1"`
	User2ID      int    `json:"user2_id" example:"2"`
	ActionUserID int    `json:"action_user_id" example:"1"`
	Status       string `json:"status" example:"pending" enums:"pending,accepted,blocked"`
}
