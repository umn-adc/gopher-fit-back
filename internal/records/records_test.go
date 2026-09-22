package records

import "testing"

func TestExerciseKey(t *testing.T) {
	for _, tt := range []struct{ name, want string }{
		{" Bench   Press ", "bench press"},
		{"\tBENCH\nPress\r", "bench press"},
		{"\u00a0DÉVELOPPÉ\u2003COUCHÉ ", "développé couché"},
		{"Push-Up", "push-up"},
		{" \t\n", ""},
	} {
		t.Run(tt.name, func(t *testing.T) {
			if got := ExerciseKey(tt.name); got != tt.want {
				t.Fatalf("ExerciseKey(%q)=%q, want=%q", tt.name, got, tt.want)
			}
		})
	}
}
