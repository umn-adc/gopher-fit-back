package db

import (
	"database/sql"
	"log"

	_ "modernc.org/sqlite"
)

func InitDB() *sql.DB {
	// os.Remove("./gopherfit.db") // Reset database

	db, err := sql.Open("sqlite", "./gopherfit.db")
	if err != nil {
		log.Fatal("failed to open database:", err)
	}

	_, err = db.Exec(`
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
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
	`)

	if err != nil {
		log.Fatal("failed to create schema:", err)
	}

	return db
}
