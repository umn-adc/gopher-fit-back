package nutrition

import (
	"net/http"
	"encoding/json"
)

func (h *Handler) addMeal(w http.ResponseWriter, r *http.Request) {
	var meal Meal

	if err := json.NewDecoder(r.Body).Decode(&meal); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	query := `
		INSERT INTO meals (user_id, date, meal_type, time, total_calories)
		VALUES (?, ?, ?, ?, ?);
	`
	_, err := h.DB.Exec(query,
		meal.UserID,
		meal.Date,
		meal.MealType,
		meal.Time,
		meal.TotalCalories,
	)
	if err != nil {
		http.Error(w, "failed to insert meal", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Meal added successfully",
	})
}
