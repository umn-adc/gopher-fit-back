package db

import (
	"database/sql"
	"log"
	"os"

	_ "modernc.org/sqlite"
)

type DB struct {
	Database *sql.DB
}

func (d *DB) InitDB() {
	os.Remove("./gopherfit.db") // Reset database

	db, err := sql.Open("sqlite", "./gopherfit.db")
	if err != nil {
		log.Fatal(err)
	}

	d.Database = db

	_, err = db.Exec(`
	CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT UNIQUE,
		password TEXT
	);

	CREATE TABLE IF NOT EXISTS macro_entries (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		date TEXT,
		calories INTEGER,
		protein INTEGER,
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
	);

	CREATE TABLE IF NOT EXISTS macro_goals (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER UNIQUE,
		calories_target INTEGER,
		protein_target INTEGER,
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
	);
	`)
	if err != nil {
		log.Fatalf("%q: %s\n", err, )
	}
}