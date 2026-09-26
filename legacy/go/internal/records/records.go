// Package records maintains personal exercise records within workout transactions.
package records

import (
	"context"
	"database/sql"
	"fmt"
	"math"
	"sort"
	"strings"
)

// ExerciseKey groups case and whitespace variants without changing workout data.
func ExerciseKey(name string) string {
	return strings.ToLower(DisplayName(name))
}

func DisplayName(name string) string {
	return strings.Join(strings.Fields(name), " ")
}

type recordKey struct {
	userID   int
	exercise string
}

type record struct {
	key      recordKey
	name     string
	weight   float64
	sourceID int
}

const candidatesSQL = `
	SELECT w.user_id, i.id, i.exercise_name, i.weight
	FROM workout_item i JOIN workouts w ON w.id = i.workout_id
	WHERE i.weight > 0`

// Backfill derives all records from existing workout items. It is called by the
// schema migration, before requests are served, in the migration transaction.
func Backfill(ctx context.Context, tx *sql.Tx) error {
	rows, err := tx.QueryContext(ctx, candidatesSQL)
	if err != nil {
		return fmt.Errorf("read historical lifts: %w", err)
	}
	best, err := bestRecords(rows, nil)
	if err != nil {
		return err
	}
	keys := make([]recordKey, 0, len(best))
	for key := range best {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].userID != keys[j].userID {
			return keys[i].userID < keys[j].userID
		}
		return keys[i].exercise < keys[j].exercise
	})
	for _, key := range keys {
		if err := saveRecord(ctx, tx, best[key]); err != nil {
			return err
		}
	}
	return nil
}

// RefreshExercises replaces only the affected exercise records for one user.
// Pass both the old and new names on rename, and the old names on deletion.
// The caller must commit this transaction together with the workout mutation.
func RefreshExercises(ctx context.Context, tx *sql.Tx, userID int, names ...string) error {
	keys := make(map[string]bool, len(names))
	for _, name := range names {
		if key := ExerciseKey(name); key != "" {
			keys[key] = true
		}
	}
	if len(keys) == 0 {
		return nil
	}
	rows, err := tx.QueryContext(ctx, candidatesSQL+` AND w.user_id = ?`, userID)
	if err != nil {
		return fmt.Errorf("read record candidates: %w", err)
	}
	best, err := bestRecords(rows, keys)
	if err != nil {
		return err
	}
	for key := range keys {
		if winner, ok := best[recordKey{userID, key}]; ok {
			if err := saveRecord(ctx, tx, winner); err != nil {
				return err
			}
		} else if _, err := tx.ExecContext(ctx, `DELETE FROM personal_records WHERE user_id = ? AND exercise_key = ?`, userID, key); err != nil {
			return fmt.Errorf("remove obsolete record: %w", err)
		}
	}
	return nil
}

// bestRecords closes the result set before callers perform more SQL on the
// same transaction. Null/blank names and nonfinite historical weights cannot rank.
func bestRecords(rows *sql.Rows, keys map[string]bool) (map[recordKey]record, error) {
	defer rows.Close()
	best := make(map[recordKey]record)
	for rows.Next() {
		var candidate record
		var name sql.NullString
		if err := rows.Scan(&candidate.key.userID, &candidate.sourceID, &name, &candidate.weight); err != nil {
			return nil, fmt.Errorf("scan record candidate: %w", err)
		}
		candidate.name = DisplayName(name.String)
		candidate.key.exercise = ExerciseKey(candidate.name)
		if candidate.key.exercise == "" || candidate.weight <= 0 || math.IsNaN(candidate.weight) || math.IsInf(candidate.weight, 0) {
			continue
		}
		if keys != nil && !keys[candidate.key.exercise] {
			continue
		}
		current, exists := best[candidate.key]
		if !exists || candidate.weight > current.weight || (candidate.weight == current.weight && candidate.sourceID < current.sourceID) {
			best[candidate.key] = candidate
		}
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate record candidates: %w", err)
	}
	if err := rows.Close(); err != nil {
		return nil, fmt.Errorf("close record candidates: %w", err)
	}
	return best, nil
}

func saveRecord(ctx context.Context, tx *sql.Tx, winner record) error {
	_, err := tx.ExecContext(ctx, `
		INSERT INTO personal_records (user_id, exercise_key, exercise_name, max_weight, source_workout_item_id)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(user_id, exercise_key) DO UPDATE SET
			exercise_name = excluded.exercise_name,
			max_weight = excluded.max_weight,
			source_workout_item_id = excluded.source_workout_item_id`,
		winner.key.userID, winner.key.exercise, winner.name, winner.weight, winner.sourceID)
	if err != nil {
		return fmt.Errorf("save personal record: %w", err)
	}
	return nil
}
