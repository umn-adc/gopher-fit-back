package db

import (
	"context"
	"database/sql"

	"gopherfit/internal/records"
)

func migratePersonalRecords(tx *sql.Tx) error {
	_, err := tx.Exec(`
		CREATE TABLE personal_records (
			user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
			exercise_key TEXT NOT NULL CHECK (length(exercise_key) > 0),
			exercise_name TEXT NOT NULL,
			max_weight REAL NOT NULL CHECK (max_weight > 0),
			source_workout_item_id INTEGER NOT NULL REFERENCES workout_item(id) ON DELETE CASCADE,
			PRIMARY KEY (user_id, exercise_key)
		);
		CREATE INDEX personal_records_exercise_weight ON personal_records (exercise_key, max_weight DESC, user_id);
		CREATE INDEX workouts_user_id ON workouts (user_id);
		CREATE INDEX workout_item_workout_id ON workout_item (workout_id);
	`)
	if err != nil {
		return err
	}
	return records.Backfill(context.Background(), tx)
}
