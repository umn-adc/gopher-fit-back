// db.go
//
// ------------------------------------------------------------
// DATABASE SETUP — DO NOT MODIFY
// ------------------------------------------------------------
//
// This file is responsible for all database setup and connection logic.
// It runs automatically when the server starts and ensures the SQLite
// database is ready for use.
//
// New members should NOT change this file.
//
// If you need to store or read data, use the provided DB variable
// (e.g., DB.Query(), DB.Exec()) from your endpoint files instead.
//
// ------------------------------------------------------------
// What this does:
// ------------------------------------------------------------
//
// 1. Opens (or creates) a SQLite database file named gopherfit.db.
// 2. Turns ON foreign key enforcement for relational integrity.
// 3. Creates the required tables if they don’t already exist:
//      - users
//      - macro_entries
//      - macro_goals
// 4. Inserts a default test user (id = 1, username = "goldy", password = "pass123") so
//    you always have a valid user to test with.
// 5. Exposes the global variable DB, which other packages use
//    to execute SQL queries.
//
// ------------------------------------------------------------

package db

import (
	"database/sql"
	"log"
	"os"

	_ "modernc.org/sqlite" // SQLite driver (do not remove)
)

// DB is the shared database connection used across the project.
// Do not reassign or close it manually anywhere else.
var DB *sql.DB

// OpenDB connects to the SQLite database and ensures all tables exist.
// Called once during server startup.
func OpenDB() (*sql.DB, error) {
	os.Remove("./gopherfit.db")
	db, err := sql.Open("sqlite", "./gopherfit.db")
	if err != nil {
		return nil, err
	}

	// Enable relational integrity (foreign keys are off by default in SQLite).
	_, _ = db.Exec(`PRAGMA foreign_keys = ON;`)

	// Core tables
	_, err = db.Exec(`
	CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT UNIQUE,
		password TEXT
	);

	CREATE TABLE IF NOT EXISTS meals (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		date TEXT NOT NULL,             -- "2025-10-30"
		meal_type TEXT NOT NULL,        -- Breakfast, Lunch, Dinner, Snack
		time TEXT,                      -- "08:30 AM"
		total_calories INTEGER DEFAULT 0,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
	);

	CREATE TABLE IF NOT EXISTS meal_items (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		meal_id INTEGER NOT NULL,
		name TEXT NOT NULL,             -- "Oatmeal with berries"
		calories INTEGER DEFAULT 0,
		protein INTEGER DEFAULT 0,
		carbs INTEGER DEFAULT 0,
		fat INTEGER DEFAULT 0,
		FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
	);



	CREATE TABLE IF NOT EXISTS macro_goals (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER UNIQUE,
		calories_target INTEGER,
		protein_target INTEGER,
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
	);
	`)

	// Default test user: goldy / pass123
	// Used for local testing before login/register endpoints are finished.
	_, err = db.Exec(`
	INSERT OR IGNORE INTO users (id, username, password)
	VALUES (1, 'goldy', 'pass123');
	`)
	if err != nil {
		log.Println("error inserting default user:", err)
	}

	if err != nil {
		return nil, err
	}

	DB = db
	return db, nil
}

// CloseDB safely closes the shared database connection.
// Called automatically when the server shuts down.
func CloseDB() {
	if DB != nil {
		if err := DB.Close(); err != nil {
			log.Println("error closing db:", err)
		}
	}
}
