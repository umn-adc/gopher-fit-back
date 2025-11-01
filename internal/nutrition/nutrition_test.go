package nutrition

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	_ "github.com/mattn/go-sqlite3"
)

// setupTestDB creates an in-memory DB with the same schema
func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatal(err)
	}

	schema := `
	CREATE TABLE meals (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		date TEXT,
		meal_type TEXT,
		time TEXT,
		total_calories INTEGER
	);
	CREATE TABLE meal_items (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		meal_id INTEGER,
		name TEXT,
		calories INTEGER,
		protein INTEGER,
		carbs INTEGER,
		fat INTEGER
	);
	`
	if _, err := db.Exec(schema); err != nil {
		t.Fatal(err)
	}

	return db
}

func TestAddMeal(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	h := NewHandler(db)

	body := []byte(`{
		"user_id": 1,
		"date": "2025-10-31",
		"meal_type": "Breakfast",
		"time": "08:30 AM",
		"total_calories": 520
	}`)

	req := httptest.NewRequest(http.MethodPost, "/api/nutrition/meals", bytes.NewReader(body))
	w := httptest.NewRecorder()

	h.addMeal(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d", w.Code)
	}

	var resp map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if resp["message"] != "Meal added successfully" {
		t.Errorf("unexpected response: %v", resp)
	}
}
