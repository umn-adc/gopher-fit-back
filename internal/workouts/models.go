package workouts

type Workout struct {
	ID          int           `json:"id" example:"1"`
	UserID      int           `json:"user_id" example:"1"`
	WorkoutName string        `json:"workout_name" example:"Morning Strength Training"`
	Duration    int           `json:"duration" example:"60"`
	Items       []WorkoutItem `json:"items,omitempty"`
}

type WorkoutItem struct {
	ID              int     `json:"id" example:"1"`
	WorkoutID       int     `json:"workout_id" example:"1"`
	ExerciseName    string  `json:"exercise_name" example:"Bench Press"`
	Sets            int     `json:"sets" example:"3"`
	Reps            int     `json:"reps" example:"10"`
	Weight          float64 `json:"weight" example:"135.5"`
	DurationMinutes float64 `json:"duration_minutes" example:"5.0"`
}
