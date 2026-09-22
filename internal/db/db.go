package db

import (
	"database/sql"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"

	_ "modernc.org/sqlite"
)

const initialSchema = `
CREATE TABLE IF NOT EXISTS users (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	username TEXT UNIQUE NOT NULL,
	password BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
	user_id INTEGER PRIMARY KEY,
	name TEXT,
	age INTEGER,
	height INTEGER,
	weight INTEGER,
	gender TEXT CHECK (gender IN ('Male', 'Female', 'Other')),
	activity_level TEXT CHECK(activity_level IN ('Sedentary', 'Lightly Active', 'Moderately Active', 'Very Active', 'Extra Active')),
	goals TEXT,
	sports TEXT,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meals (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	user_id INTEGER NOT NULL,
	date TEXT NOT NULL,
	meal_type TEXT NOT NULL,
	time TEXT,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meal_items (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	meal_id INTEGER NOT NULL,
	name TEXT NOT NULL,
	calories INTEGER DEFAULT 0,
	protein INTEGER DEFAULT 0,
	carbs INTEGER DEFAULT 0,
	fat INTEGER DEFAULT 0,
	FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS macro_goals (
	user_id INTEGER PRIMARY KEY,
	calories_target INTEGER,
	protein_target INTEGER,
	carbs_target INTEGER,
	fat_target INTEGER,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workouts (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	user_id INTEGER NOT NULL,
	workout_name TEXT,
	duration INTEGER,
	FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workout_item (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	workout_id INTEGER NOT NULL,
	exercise_name TEXT,
	sets INTEGER,
	reps INTEGER,
	weight REAL,
	duration_minutes REAL,
	FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS friendships (
	user1_id INTEGER NOT NULL,
	user2_id INTEGER NOT NULL,
	action_user_id INTEGER NOT NULL,
	status TEXT CHECK (status IN ('pending', 'accepted', 'blocked')),
	PRIMARY KEY (user1_id, user2_id),
	CHECK (user1_id < user2_id),
	FOREIGN KEY (user1_id) REFERENCES users(id) ON DELETE CASCADE,
	FOREIGN KEY (user2_id) REFERENCES users(id) ON DELETE CASCADE,
	FOREIGN KEY (action_user_id) REFERENCES users(id) ON DELETE CASCADE
);
`

type migration struct {
	version            int
	name               string
	disableForeignKeys bool
	up                 func(*sql.Tx) error
}

var migrations = []migration{
	{
		version: 1,
		name:    "initial schema",
		up: func(tx *sql.Tx) error {
			_, err := tx.Exec(initialSchema)
			return err
		},
	},
	{
		version:            2,
		name:               "store password hashes as blobs",
		disableForeignKeys: true,
		up:                 migratePasswordsToBlob,
	},
}

// InitDB opens the application's SQLite database and applies all migrations.
func InitDB() (*sql.DB, error) {
	return Open("./gopherfit.db")
}

// Open opens a SQLite database at path, enables foreign-key enforcement, and
// applies all pending migrations. A single connection keeps SQLite PRAGMA
// settings consistent for every request.
func Open(path string) (*sql.DB, error) {
	if strings.TrimSpace(path) == "" {
		return nil, fmt.Errorf("database path cannot be empty")
	}
	if err := backupExistingDatabase(path); err != nil {
		return nil, err
	}

	conn, err := sql.Open("sqlite", sqliteDSN(path))
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}
	conn.SetMaxOpenConns(1)
	conn.SetMaxIdleConns(1)

	if err := conn.Ping(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("connect to database: %w", err)
	}
	if err := setForeignKeys(conn, true); err != nil {
		conn.Close()
		return nil, err
	}
	if err := applyMigrations(conn); err != nil {
		conn.Close()
		return nil, err
	}

	return conn, nil
}

func sqliteDSN(path string) string {
	separator := "?"
	if strings.Contains(path, "?") {
		separator = "&"
	}
	return path + separator + "_pragma=foreign_keys%3dON"
}

func applyMigrations(conn *sql.DB) error {
	if _, err := conn.Exec(`
		CREATE TABLE IF NOT EXISTS schema_migrations (
			version INTEGER PRIMARY KEY,
			name TEXT NOT NULL,
			applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
		)`); err != nil {
		return fmt.Errorf("create migration table: %w", err)
	}

	for _, m := range migrations {
		var applied int
		if err := conn.QueryRow(`SELECT COUNT(*) FROM schema_migrations WHERE version = ?`, m.version).Scan(&applied); err != nil {
			return fmt.Errorf("check migration %d: %w", m.version, err)
		}
		if applied != 0 {
			continue
		}
		if err := applyMigration(conn, m); err != nil {
			return err
		}
	}

	return nil
}

func applyMigration(conn *sql.DB, m migration) (returnErr error) {
	if m.disableForeignKeys {
		if err := setForeignKeys(conn, false); err != nil {
			return fmt.Errorf("disable foreign keys for migration %d: %w", m.version, err)
		}
		defer func() {
			if err := setForeignKeys(conn, true); err != nil && returnErr == nil {
				returnErr = fmt.Errorf("re-enable foreign keys after migration %d: %w", m.version, err)
			}
		}()
	}

	tx, err := conn.Begin()
	if err != nil {
		return fmt.Errorf("begin migration %d: %w", m.version, err)
	}
	defer func() {
		if err := tx.Rollback(); err != nil && err != sql.ErrTxDone && returnErr == nil {
			returnErr = fmt.Errorf("roll back migration %d: %w", m.version, err)
		}
	}()

	if err := m.up(tx); err != nil {
		return fmt.Errorf("apply migration %d (%s): %w", m.version, m.name, err)
	}
	if err := checkForeignKeys(tx); err != nil {
		return fmt.Errorf("validate migration %d foreign keys: %w", m.version, err)
	}
	if _, err := tx.Exec(`INSERT INTO schema_migrations (version, name) VALUES (?, ?)`, m.version, m.name); err != nil {
		return fmt.Errorf("record migration %d: %w", m.version, err)
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("commit migration %d: %w", m.version, err)
	}
	log.Printf("applied database migration %d (%s)", m.version, m.name)

	return nil
}

func backupExistingDatabase(path string) (returnErr error) {
	if path == ":memory:" || strings.HasPrefix(path, "file:") {
		return nil
	}

	sourceInfo, err := os.Stat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("inspect database before migration: %w", err)
	}
	if !sourceInfo.Mode().IsRegular() {
		return fmt.Errorf("database path is not a regular file: %s", path)
	}

	backupPath := path + ".pre-migrations.bak"
	if backupInfo, err := os.Stat(backupPath); err == nil {
		if !backupInfo.Mode().IsRegular() {
			return fmt.Errorf("database backup path is not a regular file: %s", backupPath)
		}
		return nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("inspect database backup: %w", err)
	}

	source, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open database for backup: %w", err)
	}
	defer func() {
		if err := source.Close(); err != nil && returnErr == nil {
			returnErr = fmt.Errorf("close database backup source: %w", err)
		}
	}()

	backupDir := filepath.Dir(backupPath)
	temporary, err := os.CreateTemp(backupDir, filepath.Base(backupPath)+".*.tmp")
	if err != nil {
		return fmt.Errorf("create temporary database backup: %w", err)
	}
	temporaryPath := temporary.Name()
	temporaryClosed := false
	defer os.Remove(temporaryPath)
	defer func() {
		if !temporaryClosed {
			if err := temporary.Close(); err != nil && returnErr == nil {
				returnErr = fmt.Errorf("close temporary database backup: %w", err)
			}
		}
	}()

	if err := temporary.Chmod(sourceInfo.Mode().Perm()); err != nil {
		return fmt.Errorf("set database backup permissions: %w", err)
	}
	if _, err := io.Copy(temporary, source); err != nil {
		return fmt.Errorf("copy database backup: %w", err)
	}
	if err := temporary.Sync(); err != nil {
		return fmt.Errorf("sync database backup: %w", err)
	}
	if err := temporary.Close(); err != nil {
		return fmt.Errorf("close database backup: %w", err)
	}
	temporaryClosed = true
	if err := os.Rename(temporaryPath, backupPath); err != nil {
		return fmt.Errorf("install database backup: %w", err)
	}
	log.Printf("created pre-migration database backup at %s", backupPath)
	return nil
}

func migratePasswordsToBlob(tx *sql.Tx) error {
	columnType, err := passwordColumnType(tx)
	if err != nil {
		return err
	}
	if strings.EqualFold(columnType, "BLOB") {
		return nil
	}

	_, err = tx.Exec(`
		CREATE TABLE users_new (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT UNIQUE NOT NULL,
			password BLOB NOT NULL
		);
		INSERT INTO users_new (id, username, password)
			SELECT id, username, CAST(password AS BLOB) FROM users;
		DROP TABLE users;
		ALTER TABLE users_new RENAME TO users;
	`)
	return err
}

func passwordColumnType(tx *sql.Tx) (string, error) {
	rows, err := tx.Query(`PRAGMA table_info(users)`)
	if err != nil {
		return "", fmt.Errorf("inspect users table: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var cid, notNull, primaryKey int
		var name, columnType string
		var defaultValue any
		if err := rows.Scan(&cid, &name, &columnType, &notNull, &defaultValue, &primaryKey); err != nil {
			return "", fmt.Errorf("scan users schema: %w", err)
		}
		if name == "password" {
			return columnType, nil
		}
	}
	if err := rows.Err(); err != nil {
		return "", fmt.Errorf("iterate users schema: %w", err)
	}
	return "", fmt.Errorf("users.password column not found")
}

func setForeignKeys(conn *sql.DB, enabled bool) error {
	value := "OFF"
	expected := 0
	if enabled {
		value = "ON"
		expected = 1
	}
	if _, err := conn.Exec("PRAGMA foreign_keys = " + value); err != nil {
		return fmt.Errorf("set foreign keys %s: %w", value, err)
	}

	var actual int
	if err := conn.QueryRow(`PRAGMA foreign_keys`).Scan(&actual); err != nil {
		return fmt.Errorf("read foreign-key setting: %w", err)
	}
	if actual != expected {
		return fmt.Errorf("foreign-key setting is %d, expected %d", actual, expected)
	}
	return nil
}

func checkForeignKeys(tx *sql.Tx) error {
	rows, err := tx.Query(`PRAGMA foreign_key_check`)
	if err != nil {
		return err
	}
	defer rows.Close()

	if rows.Next() {
		var table string
		var rowID int64
		var parent string
		var constraintID int
		if err := rows.Scan(&table, &rowID, &parent, &constraintID); err != nil {
			return err
		}
		err := fmt.Errorf("foreign-key violation in %s row %d referencing %s", table, rowID, parent)
		log.Printf("database migration validation failed: %v", err)
		return err
	}
	return rows.Err()
}
