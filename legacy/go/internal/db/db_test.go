package db

import (
	"database/sql"
	"path/filepath"
	"testing"
)

func TestOpenCreatesMigratedSchemaAndEnforcesForeignKeys(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fresh.db")
	conn, err := Open(path)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	defer conn.Close()

	assertForeignKeysEnabled(t, conn)
	assertPasswordColumnType(t, conn, "BLOB")
	assertMigrationCount(t, conn, len(migrations))

	// Force database/sql to replace the original connection. The DSN must
	// enable foreign keys for replacement connections as well.
	conn.SetMaxIdleConns(0)
	assertForeignKeysEnabled(t, conn)

	result, err := conn.Exec(`INSERT INTO users (username, password) VALUES (?, ?)`, "gopher", []byte("hash"))
	if err != nil {
		t.Fatalf("insert user: %v", err)
	}
	userID, err := result.LastInsertId()
	if err != nil {
		t.Fatalf("read user ID: %v", err)
	}
	if _, err := conn.Exec(`INSERT INTO profiles (user_id, gender) VALUES (?, ?)`, userID, "Other"); err != nil {
		t.Fatalf("insert profile: %v", err)
	}
	if _, err := conn.Exec(`DELETE FROM users WHERE id = ?`, userID); err != nil {
		t.Fatalf("delete user: %v", err)
	}

	var profiles int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM profiles WHERE user_id = ?`, userID).Scan(&profiles); err != nil {
		t.Fatalf("count profiles: %v", err)
	}
	if profiles != 0 {
		t.Fatalf("profile count after user deletion = %d, want 0", profiles)
	}

	if err := conn.Close(); err != nil {
		t.Fatalf("close database: %v", err)
	}
	conn, err = Open(path)
	if err != nil {
		t.Fatalf("second Open() error = %v", err)
	}
	defer conn.Close()
	assertMigrationCount(t, conn, len(migrations))
}

func TestOpenMigratesLegacyTextPasswordWithoutLosingRelations(t *testing.T) {
	path := filepath.Join(t.TempDir(), "legacy.db")
	legacy, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatalf("open legacy database: %v", err)
	}
	_, err = legacy.Exec(`
		CREATE TABLE users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT UNIQUE NOT NULL,
			password TEXT NOT NULL
		);
		CREATE TABLE profiles (
			user_id INTEGER PRIMARY KEY,
			name TEXT,
			FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
		);
		INSERT INTO users (id, username, password) VALUES (7, 'legacy', 'legacy-hash');
		INSERT INTO profiles (user_id, name) VALUES (7, 'Legacy User');
	`)
	if err != nil {
		legacy.Close()
		t.Fatalf("create legacy schema: %v", err)
	}
	if err := legacy.Close(); err != nil {
		t.Fatalf("close legacy database: %v", err)
	}

	conn, err := Open(path)
	if err != nil {
		t.Fatalf("Open() legacy error = %v", err)
	}
	defer conn.Close()

	backup, err := sql.Open("sqlite", path+".pre-migrations.bak")
	if err != nil {
		t.Fatalf("open pre-migration backup: %v", err)
	}
	defer backup.Close()
	assertPasswordColumnType(t, backup, "TEXT")

	assertPasswordColumnType(t, conn, "BLOB")
	assertForeignKeysEnabled(t, conn)
	assertMigrationCount(t, conn, len(migrations))

	var username string
	var password []byte
	if err := conn.QueryRow(`SELECT username, password FROM users WHERE id = 7`).Scan(&username, &password); err != nil {
		t.Fatalf("read migrated user: %v", err)
	}
	if username != "legacy" || string(password) != "legacy-hash" {
		t.Fatalf("migrated user = (%q, %q), want (legacy, legacy-hash)", username, password)
	}

	var profileName string
	if err := conn.QueryRow(`SELECT name FROM profiles WHERE user_id = 7`).Scan(&profileName); err != nil {
		t.Fatalf("read migrated profile: %v", err)
	}
	if profileName != "Legacy User" {
		t.Fatalf("profile name = %q, want Legacy User", profileName)
	}

	result, err := conn.Exec(`INSERT INTO users (username, password) VALUES (?, ?)`, "post-migration", []byte("hash"))
	if err != nil {
		t.Fatalf("insert post-migration user: %v", err)
	}
	newID, err := result.LastInsertId()
	if err != nil {
		t.Fatalf("read post-migration user ID: %v", err)
	}
	if newID <= 7 {
		t.Fatalf("post-migration user ID = %d, want greater than preserved ID 7", newID)
	}
}

func assertForeignKeysEnabled(t *testing.T, conn *sql.DB) {
	t.Helper()
	var enabled int
	if err := conn.QueryRow(`PRAGMA foreign_keys`).Scan(&enabled); err != nil {
		t.Fatalf("read foreign_keys: %v", err)
	}
	if enabled != 1 {
		t.Fatalf("foreign_keys = %d, want 1", enabled)
	}
}

func assertPasswordColumnType(t *testing.T, conn *sql.DB, want string) {
	t.Helper()
	rows, err := conn.Query(`PRAGMA table_info(users)`)
	if err != nil {
		t.Fatalf("inspect users schema: %v", err)
	}
	defer rows.Close()

	for rows.Next() {
		var cid, notNull, primaryKey int
		var name, columnType string
		var defaultValue any
		if err := rows.Scan(&cid, &name, &columnType, &notNull, &defaultValue, &primaryKey); err != nil {
			t.Fatalf("scan users schema: %v", err)
		}
		if name == "password" {
			if columnType != want {
				t.Fatalf("password column type = %q, want %q", columnType, want)
			}
			return
		}
	}
	t.Fatal("password column not found")
}

func assertMigrationCount(t *testing.T, conn *sql.DB, want int) {
	t.Helper()
	var count int
	if err := conn.QueryRow(`SELECT COUNT(*) FROM schema_migrations`).Scan(&count); err != nil {
		t.Fatalf("count migrations: %v", err)
	}
	if count != want {
		t.Fatalf("migration count = %d, want %d", count, want)
	}
}
