package db

import (
	"database/sql"
	"log"
	"os"

	_ "modernc.org/sqlite"
)

func InitDB() *sql.DB {
	os.Remove("./gopherfit.db") // Reset database

	db, err := sql.Open("sqlite", "./gopherfit.db")
	if err != nil {
		log.Fatal("failed to open database:", err)
	}

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
		carbs_target INTEGER,
		fat_target INTEGER,
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
	);
	`)

	if err != nil {
		log.Fatal("failed to create schema:", err)
	}

	return db
}