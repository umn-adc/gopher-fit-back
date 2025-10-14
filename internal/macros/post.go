package macros

// ADD "encoding/json" and "gopherfit/internal/db" when your endpoints require them.
import (
	"net/http"
	"encoding/json"
	"gopherfit/internal/db"
)

// handlePostMacros handles POST /api/macros requests.
//
// ------------------------------------------------------------
// OVERVIEW
// ------------------------------------------------------------
// This endpoint receives JSON data representing a user's daily macros,
// validates the required fields, saves the data to the SQLite database,
// and returns the same data back as a JSON confirmation.
//
// Example request body:
//   {
//     "user_id": 1,
//     "date": "2025-10-14",
//     "calories": 500,
//     "protein": 30
//   }
//
// Example response:
//   {
//     "user_id": 1,
//     "date": "2025-10-14",
//     "calories": 500,
//     "protein": 30
//   }
//
// ------------------------------------------------------------
// STEP-BY-STEP
// ------------------------------------------------------------
// 1. Decode JSON input into a Go struct (MacrosData).
// 2. Validate that required fields (like user_id) are present.
// 3. Execute a SQL query to insert or update a row in macro_entries.
// 4. Send a JSON response back to the client.
//
// ------------------------------------------------------------
// DATABASE BEHAVIOR
// ------------------------------------------------------------
// - The SQL statement uses INSERT OR REPLACE, which means:
//     • If a row with the same (user_id, date) exists, it will be updated.
//     • Otherwise, a new row will be created.
// - The macro_entries table should include:
//     id (INTEGER PRIMARY KEY AUTOINCREMENT) (AUTOMATICALLY CREATED),
//     user_id (INTEGER),
//     date (TEXT),
//     calories (INTEGER),
//     protein (INTEGER).
//
// ------------------------------------------------------------
func handlePostMacros(w http.ResponseWriter, r *http.Request) {
	// Step 1: Decode incoming JSON into the MacrosData struct. This is in the shared macros namespace. Find in macros/model.go
	var input MacrosData
	_ = json.NewDecoder(r.Body).Decode(&input)

	// Step 2: Validate required fields.
	if input.UserID == 0 {
		http.Error(w, "user_id is required", http.StatusBadRequest)
		return
	}

	// Step 3: Execute SQL insert or update using SQLite.
	// db.DB.Exec creates an executable SQL statement to the database
	// The question marks in VALUES (?, ?, ?, ?) mean that the following parameters (input.UserID, ...) map to those ?'s
	db.DB.Exec(`
		INSERT OR REPLACE INTO macro_entries (user_id, date, calories, protein)
		VALUES (?, ?, ?, ?)
	`, input.UserID, input.Date, input.Calories, input.Protein)

	// Step 4: Send back a JSON confirmation with the same data.
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(input)
}
