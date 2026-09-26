package db

import (
	"database/sql"
	"math"
	"reflect"
	"testing"
)

func TestPersonalRecordsMigrationBackfillsAndPreservesHistory(t *testing.T) {
	conn := recordMigrationDB(t)
	execRecordFixture(t, conn, `
		INSERT INTO users (id, username, password) VALUES (1, 'one', X'01'), (2, 'two', X'02');
		INSERT INTO workouts (id, user_id, workout_name, duration) VALUES (10, 1, 'First', 30), (11, 1, 'Second', 30), (20, 2, 'Other', 30);
		INSERT INTO workout_item (id, workout_id, exercise_name, weight) VALUES
			(1, 10, 'Bench Press', 100), (3, 11, 'bench press', 125.5),
			(4, 10, 'Squat', 200), (5, 20, 'BENCH PRESS', 90),
			(6, 10, 'Cardio', 0), (7, 10, 'Negative', -10),
			(8, 10, '   ', 200), (9, 10, NULL, 300), (10, 10, 'Unknown', NULL);
	`)
	// The earlier ID wins a tie even when the case and Unicode whitespace differ.
	execRecordFixture(t, conn, `INSERT INTO workout_item (id, workout_id, exercise_name, weight) VALUES (2, 10, ?, ?)`, " \tBENCH\u00a0PRESS \n", 125.5)
	execRecordFixture(t, conn, `INSERT INTO workout_item (id, workout_id, exercise_name, weight) VALUES (11, 10, 'Infinite', ?)`, math.Inf(1))
	if err := applyMigrations(conn); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	assertMigrationCount(t, conn, 3)
	type result struct {
		userID    int
		key, name string
		weight    float64
		sourceID  int
	}
	readRecords := func() []result {
		t.Helper()
		rows, err := conn.Query(`SELECT user_id, exercise_key, exercise_name, max_weight, source_workout_item_id FROM personal_records ORDER BY user_id, exercise_key`)
		if err != nil {
			t.Fatal(err)
		}
		defer rows.Close()
		var got []result
		for rows.Next() {
			var row result
			if err := rows.Scan(&row.userID, &row.key, &row.name, &row.weight, &row.sourceID); err != nil {
				t.Fatal(err)
			}
			got = append(got, row)
		}
		if err := rows.Err(); err != nil {
			t.Fatal(err)
		}
		return got
	}
	want := []result{{1, "bench press", "BENCH PRESS", 125.5, 2}, {1, "squat", "Squat", 200, 4}, {2, "bench press", "BENCH PRESS", 90, 5}}
	if got := readRecords(); !reflect.DeepEqual(got, want) {
		t.Fatalf("records=%+v, want=%+v", got, want)
	}
	if err := applyMigrations(conn); err != nil {
		t.Fatalf("reapply: %v", err)
	}
	if got := readRecords(); !reflect.DeepEqual(got, want) {
		t.Fatalf("reapplying changed records: %+v", got)
	}
	var count int
	var originalName string
	if err := conn.QueryRow(`SELECT COUNT(*) FROM workout_item`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if err := conn.QueryRow(`SELECT exercise_name FROM workout_item WHERE id = 2`).Scan(&originalName); err != nil {
		t.Fatal(err)
	}
	if count != 11 || originalName != " \tBENCH\u00a0PRESS \n" {
		t.Fatalf("historical rows changed: count=%d name=%q", count, originalName)
	}
	rows, err := conn.Query(`PRAGMA foreign_key_check`)
	if err != nil {
		t.Fatal(err)
	}
	if rows.Next() {
		t.Fatal("foreign-key violation after backfill")
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	if err := rows.Close(); err != nil {
		t.Fatal(err)
	}

	execRecordFixture(t, conn, `DELETE FROM users WHERE id = 1`)
	if err := conn.QueryRow(`SELECT COUNT(*) FROM personal_records WHERE user_id = 1`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 0 {
		t.Fatalf("user deletion left %d records", count)
	}
	if err := conn.QueryRow(`SELECT COUNT(*) FROM personal_records WHERE user_id = 2`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatal("user deletion changed another user's record")
	}
}

func TestPersonalRecordsMigrationRollsBackOnInvalidHistory(t *testing.T) {
	conn := recordMigrationDB(t)
	execRecordFixture(t, conn, `PRAGMA foreign_keys = OFF`)
	execRecordFixture(t, conn, `INSERT INTO workouts (id, user_id) VALUES (1, 99); INSERT INTO workout_item (id, workout_id, exercise_name, weight) VALUES (1, 1, 'Squat', 100)`)
	execRecordFixture(t, conn, `PRAGMA foreign_keys = ON`)
	if err := applyMigrations(conn); err == nil {
		t.Fatal("expected migration to reject orphaned data")
	}
	assertMigrationCount(t, conn, 2)
	var count int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM sqlite_master WHERE name = 'personal_records'`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 0 {
		t.Fatal("failed migration left a partial record schema")
	}
	if err := conn.QueryRow(`SELECT COUNT(*) FROM workout_item`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatal("failed migration deleted historical data")
	}
	// Once the existing inconsistency is resolved, the same migration can retry.
	execRecordFixture(t, conn, `INSERT INTO users (id, username, password) VALUES (99, 'recovered', X'01')`)
	if err := applyMigrations(conn); err != nil {
		t.Fatalf("retry migration: %v", err)
	}
	assertMigrationCount(t, conn, 3)
}

func recordMigrationDB(t *testing.T) *sql.DB {
	t.Helper()
	conn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	conn.SetMaxOpenConns(1)
	t.Cleanup(func() {
		if err := conn.Close(); err != nil {
			t.Error(err)
		}
	})
	execRecordFixture(t, conn, `PRAGMA foreign_keys = ON`)
	execRecordFixture(t, conn, initialSchema)
	execRecordFixture(t, conn, `CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL); INSERT INTO schema_migrations VALUES (1, 'initial schema'), (2, 'store password hashes as blobs')`)
	return conn
}

func execRecordFixture(t *testing.T, conn *sql.DB, query string, args ...any) {
	t.Helper()
	if _, err := conn.Exec(query, args...); err != nil {
		t.Fatal(err)
	}
}
