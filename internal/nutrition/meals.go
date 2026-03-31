package nutrition

import (
	"net/http"

	"gopherfit/internal/api"
)

// @Summary Get user meals
// @Tags nutrition
// @Security BearerAuth
// @Success 200 {array} Meal
// @Router /nutrition/meals [get]
func (h *Handler) getUserMeals(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	rows, err := h.DB.Query(`
		SELECT m.id, m.user_id, m.date, m.meal_type, m.time,
		       COALESCE(SUM(mi.calories), 0) AS total_calories
		FROM meals m
		LEFT JOIN meal_items mi ON mi.meal_id = m.id
		WHERE m.user_id = ?
		GROUP BY m.id`, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch meals", err)
		return
	}

	meals := []Meal{}
	for rows.Next() {
		var m Meal
		rows.Scan(&m.ID, &m.UserID, &m.Date, &m.MealType, &m.Time, &m.TotalCalories)
		m.Items = []MealItem{}
		meals = append(meals, m)
	}
	rows.Close()

	for i := range meals {
		itemRows, err := h.DB.Query(`
			SELECT id, meal_id, name, calories, protein, carbs, fat
			FROM meal_items WHERE meal_id = ?`, meals[i].ID)
		if err != nil {
			api.WriteError(w, http.StatusInternalServerError, "failed to fetch meal items", err)
			return
		}
		for itemRows.Next() {
			var item MealItem
			itemRows.Scan(&item.ID, &item.MealID, &item.Name, &item.Calories, &item.Protein, &item.Carbs, &item.Fat)
			meals[i].Items = append(meals[i].Items, item)
		}
		itemRows.Close()
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
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	var meal Meal
	if !api.DecodeJSON(w, r, &meal) {
		return
	}

	res, err := h.DB.Exec(`
		INSERT INTO meals (user_id, date, meal_type, time)
		VALUES (?, ?, ?, ?);
	`, userID, meal.Date, meal.MealType, meal.Time)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert meal", err)
		return
	}

	id, _ := res.LastInsertId()
	meal.ID = int(id)
	meal.UserID = userID
	meal.Items = []MealItem{}
	api.WriteSuccess(w, http.StatusCreated, meal)
}

// @Summary Get meal by ID
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Success 200 {object} Meal
// @Router /nutrition/meals/{id} [get]
func (h *Handler) getMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	mealID, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	var meal Meal
	err := h.DB.QueryRow(`SELECT id, user_id, date, meal_type, time FROM meals WHERE id = ? AND user_id = ?`, mealID, userID).
		Scan(&meal.ID, &meal.UserID, &meal.Date, &meal.MealType, &meal.Time)
	if err != nil {
		api.WriteError(w, http.StatusNotFound, "Meal not found", err)
		return
	}

	itemRows, err := h.DB.Query(`SELECT id, meal_id, name, calories, protein, carbs, fat FROM meal_items WHERE meal_id = ?`, mealID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Failed to fetch meal items", err)
		return
	}
	defer itemRows.Close()

	meal.Items = []MealItem{}
	for itemRows.Next() {
		var item MealItem
		itemRows.Scan(&item.ID, &item.MealID, &item.Name, &item.Calories, &item.Protein, &item.Carbs, &item.Fat)
		meal.Items = append(meal.Items, item)
		meal.TotalCalories += item.Calories
	}

	api.WriteSuccess(w, http.StatusOK, meal)
}

// @Summary Add item to meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param request body MealItem true "Meal item data"
// @Success 201 {object} MealItem
// @Router /nutrition/meals/{id}/items [post]
func (h *Handler) addMealItem(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	mealID, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	var mealItem MealItem
	if !api.DecodeJSON(w, r, &mealItem) {
		return
	}

	res, err := h.DB.Exec(`
		INSERT INTO meal_items (meal_id, name, calories, protein, carbs, fat)
		SELECT ?, ?, ?, ?, ?, ? WHERE EXISTS (
			SELECT 1 FROM meals WHERE id = ? AND user_id = ?
		)`, mealID, mealItem.Name, mealItem.Calories, mealItem.Protein, mealItem.Carbs, mealItem.Fat, mealID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to insert meal item", err)
		return
	}

	if !api.CheckAffected(w, res, "Meal not found") {
		return
	}

	id, _ := res.LastInsertId()
	mealItem.ID = int(id)
	mealItem.MealID = mealID
	api.WriteSuccess(w, http.StatusCreated, mealItem)
}

// @Summary Update meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param request body Meal true "Meal data"
// @Success 200 {object} Meal
// @Router /nutrition/meals/{id} [put]
func (h *Handler) updateMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	mealID, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	var meal Meal
	if !api.DecodeJSON(w, r, &meal) {
		return
	}

	res, err := h.DB.Exec(`UPDATE meals SET date = ?, meal_type = ?, time = ? WHERE id = ? AND user_id = ?`,
		meal.Date, meal.MealType, meal.Time, mealID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to update meal", err)
		return
	}

	if !api.CheckAffected(w, res, "Meal not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// @Summary Delete meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Success 204 "No Content"
// @Router /nutrition/meals/{id} [delete]
func (h *Handler) deleteMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := api.GetUserID(w, r)
	if !ok {
		return
	}

	mealID, ok := api.PathInt(w, r, "id")
	if !ok {
		return
	}

	res, err := h.DB.Exec(`DELETE FROM meals WHERE id = ? AND user_id = ?`, mealID, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to delete meal", err)
		return
	}

	if !api.CheckAffected(w, res, "Meal not found") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
