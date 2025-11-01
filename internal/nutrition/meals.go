package nutrition

import (
	"net/http"
	"encoding/json"
)

// TODO:
// Add JWT authorization. 
// All functions should verify that the user is only editing/getting their information.

func (h *Handler) getUserMeals(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		http.Error(w, "user_id required", http.StatusBadRequest)
		return
	}

	rows, err := h.DB.Query("SELECT * FROM meals WHERE user_id = ?", userID)
	if err != nil {
		http.Error(w, "failed to fetch meals", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var meals []Meal
	for rows.Next() {
		var m Meal
		rows.Scan(&m.ID, &m.UserID, &m.Date, &m.MealType, &m.Time, &m.TotalCalories)
		meals = append(meals, m)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(meals)
}

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

func (h *Handler) addMealItem(w http.ResponseWriter, r *http.Request) {
	var mealItem MealItem

	if err := json.NewDecoder(r.Body).Decode(&mealItem); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	query := `
		INSERT INTO meal_items (meal_id, name, calories, protein, carbs, fat)
		VALUES (?, ?, ?, ?, ?, ?);
	`
	_, err := h.DB.Exec(query,
		mealItem.meal_id,
		mealItem.name,
		mealItem.calories,
		mealItem.protein,
		mealItem.carbs,
		mealItem.fat,
	)
	if err != nil {
		http.Error(w, "failed to insert meal item", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Meal item added successfully",
	})
}