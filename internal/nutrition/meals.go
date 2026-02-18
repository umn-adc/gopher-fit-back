package nutrition

import (
	"encoding/json"
	"net/http"
	"strconv"
	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
)

// @Summary Get user meals
// @Tags nutrition
// @Security BearerAuth
// @Success 200 {array} Meal
// @Router /nutrition/meals [get]
func (h *Handler) getUserMeals(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	rows, err := h.DB.Query("SELECT * FROM meals WHERE user_id = ?", userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch meals", err)
		return
	}
	defer rows.Close()

	var meals []Meal
	for rows.Next() {
		var m Meal
		rows.Scan(&m.ID, &m.UserID, &m.Date, &m.MealType, &m.Time, &m.TotalCalories)
		meals = append(meals, m)
	}

	api.WriteSuccess(w, http.StatusOK, meals)
}

// @Summary Create a meal
// @Tags nutrition
// @Security BearerAuth
// @Param request body Meal true "Meal data"
// @Success 201 {object} Meal
// @Router /nutrition/meals [post]
func (h *Handler) addMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	var meal Meal
	if err := json.NewDecoder(r.Body).Decode(&meal); err != nil {
		api.WriteError(w, http.StatusBadRequest, "invalid JSON", err)
		return
	}

	query := `
		INSERT INTO meals (user_id, date, meal_type, time, total_calories)
		VALUES (?, ?, ?, ?, ?);
	`
	_, err := h.DB.Exec(query,
		userID,
		meal.Date,
		meal.MealType,
		meal.Time,
		meal.TotalCalories,
	)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert meal", err)
		return
	}

	api.WriteSuccess(w, http.StatusCreated, map[string]string{"message": "Meal added successfully"})
}

// @Summary Add item to meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param request body MealItem true "Meal item data"
// @Success 201 {object} MealItem
// @Router /nutrition/meals/{id}/items [post]
func (h *Handler) addMealItem(w http.ResponseWriter, r *http.Request) {
	var mealItem MealItem

	if err := json.NewDecoder(r.Body).Decode(&mealItem); err != nil {
		api.WriteError(w, http.StatusBadRequest, "invalid JSON", err)
		return
	}

	query := `
		INSERT INTO meal_items (meal_id, name, calories, protein, carbs, fat)
		VALUES (?, ?, ?, ?, ?, ?);
	`
	_, err := h.DB.Exec(query,
		mealItem.MealID,
		mealItem.Name,
		mealItem.Calories,
		mealItem.Protein,
		mealItem.Carbs,
		mealItem.Fat,
	)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert meal item", err)
		return
	}

	api.WriteSuccess(w, http.StatusCreated, map[string]string{"message": "Meal item added successfully"})
}

// @Summary Get meal by ID
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Success 200 {object} Meal
// @Router /nutrition/meals/{id} [get]
func (h *Handler) getMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	meal_id, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid meal ID", err)
		return
	}

	var meal Meal

	err = h.DB.QueryRow(`SELECT id, user_id, date, meal_type, time, total_calories FROM meals WHERE id = ? AND user_id = ?`, meal_id, userID).
		Scan(&meal.ID, &meal.UserID, &meal.Date, &meal.MealType, &meal.Time, &meal.TotalCalories)
	if err != nil {
		api.WriteError(w, http.StatusNotFound, "Meal not found", err)
		return
	}

	itemRows, err := h.DB.Query(`SELECT id, meal_id, name, calories, protein, carbs, fat FROM meal_items WHERE meal_id = ?`, meal_id)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch meal items", err)
		return
	}
	defer itemRows.Close()

	for itemRows.Next() {
		var item MealItem
		itemRows.Scan(&item.ID, &item.MealID, &item.Name, &item.Calories, &item.Protein, &item.Carbs, &item.Fat)
		meal.Items = append(meal.Items, item)
	}

	api.WriteSuccess(w, http.StatusOK, meal)
}





// @Summary Update meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param request body Meal true "Meal data"
// @Success 200 {object} Meal
// @Router /nutrition/meals/{id} [put]
func (h *Handler) updateMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	mealID, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid meal ID", err)
		return
	}

	var meal Meal
	if err := json.NewDecoder(r.Body).Decode(&meal); err != nil {
		api.WriteError(w, http.StatusBadRequest, "invalid JSON", err)
		return
	}

	query := `UPDATE meals SET date = ?, meal_type = ?, time = ?, total_calories = ? WHERE id = ? AND user_id = ?`
	res, err := h.DB.Exec(query, meal.Date, meal.MealType, meal.Time, meal.TotalCalories, mealID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to update meal", err)
		return
	}

	rowsAffected, err := res.RowsAffected()
	if err != nil || rowsAffected == 0 {
		api.WriteError(w, http.StatusNotFound, "Meal not found", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, map[string]string{"message": "Meal updated successfully"})
}

// @Summary Delete meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Success 204 "No Content"
// @Router /nutrition/meals/{id} [delete]
func (h *Handler) deleteMeal(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
	// delete meal and meal items (under meal class)

	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	mealID := r.PathValue("id")
	if mealID == "" {
		api.WriteError(w, http.StatusBadRequest, "invalid id", nil)
		return
	}

	query := `DELETE FROM meals WHERE meal_id = ? AND user_id = ?`

	res, err := h.DB.Exec(query, mealID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete meal", err)
		return
	}

	rowsAffected, err := res.RowsAffected()
	if err != nil || rowsAffected == 0 {
		api.WriteError(w, http.StatusNotFound, "meal not found", err)
		return

	}

	w.WriteHeader(http.StatusNoContent)

}
