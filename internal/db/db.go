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
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS user_details (
		user_id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER,
        height INTEGER,
        weight INTEGER,
        gender TEXT CHECK (gender IN ('Male', 'Female', 'Other')),
        activity_level TEXT CHECK(activity_level IN ('Sedentary', 'Lightly Active', 'Moderately Active', 'Very Active', 'Extra Active')),
		FOREIGN KEY (user_id) REFERENCES users(id)
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

	CREATE TABlE IF NOT EXISTS goals (
		goal TEXT NOT NULL CHECK(goal IN ('Lose Weight', 'Build Muscle', 'Increase Endurance', 'Improve Flexibility',
											'General Fitness', 'Athletic Performance', 'Rehab/Recovery', 'Maintain Weight')),
		details TEXT,
		PRIMARY KEY (goal)
	);
	INSERT INTO goals (goal) VALUES
		('Lose Weight'), ('Build Muscle'), ('Increase Endurance'), ('Improve Flexibility'),
		('General Fitness'), ('Athletic Performance'), ('Rehab/Recovery'), ('Maintain Weight');

	CREATE TABLE IF NOT EXISTS user_goals (
		user_id INTEGER NOT NULL,
		goal TEXT NOT NULL,
		PRIMARY KEY (user_id, goal),
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
		FOREIGN KEY (goal) REFERENCES goals(goal) ON DELETE CASCADE
	);

	CREATE TABLE IF NOT EXISTS sports (
		sport TEXT NOT NULL CHECK(sport IN ('Football', 'Basketball', 'Hockey', 'Soccer', 'Volleyball',
											'Baseball', 'Softball', 'Track & Field', 'Swimming', 'Wrestling',
											'Gymnastics', 'Martial Arts')),
		PRIMARY KEY (sport)
	);
	INSERT INTO sports (sport) VALUES
		('Football'), ('Basketball'), ('Hockey'), ('Soccer'), ('Volleyball'),
		('Baseball'), ('Softball'), ('Track & Field'), ('Swimming'), ('Wrestling'),
		('Gymnastics'), ('Martial Arts');

	CREATE TABLE IF NOT EXISTS user_sports (
		user_id INTEGER NOT NULL,
		sport TEXT NOT NULL,
		PRIMARY KEY (user_id, sport),
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
		FOREIGN KEY (sport) REFERENCES sports(sport) ON DELETE CASCADE
	);
	`)

	if err != nil {
		log.Fatal("failed to create schema:", err)
	}

	return db
}
