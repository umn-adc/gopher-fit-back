package nutrition

import (
	"encoding/json"
	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
	"net/http"
	"strconv"
)

func getFavoriteMealHelper(h *Handler, id int, userID int) (Meal, error) {
	var meal Meal
	err := h.DB.QueryRow(`SELECT id, user_id, date, meal_type, time, total_calories FROM favorite_meals WHERE id = ? AND user_id = ?`, id, userID).
		Scan(&meal.ID, &meal.UserID, &meal.Date, &meal.MealType, &meal.Time, &meal.TotalCalories)

	if err != nil {
		return meal, err
	}

	rows, err := h.DB.Query(`SELECT id, meal_id, name, calories, protein, carbs, fat FROM favorite_meal_items WHERE meal_id = ?`, id)
	if err != nil {
		return meal, err
	}
	defer rows.Close()

	for rows.Next() {
		var item MealItem
		err = rows.Scan(&item.ID, &item.MealID, &item.Name, &item.Calories, &item.Protein, &item.Carbs, &item.Fat)
		if err != nil {
			return meal, err
		}
		meal.Items = append(meal.Items, item)
	}
	return meal, nil
}

func addFavMealHelper(h *Handler, meal Meal) error {
	query := `
		INSERT INTO favorite_meals (user_id, date, meal_type, time, total_calories)
		VALUES (?, ?, ?, ?, ?)
		RETURNING id;
	`
	var id int
	err := h.DB.QueryRow(query, meal.UserID, meal.Date, meal.Time, meal.TotalCalories).Scan(&id)

	if err != nil {
		return err
	}

	query = `
		INSERT INTO favorite_meal_items (meal_id, name, calories, protein, carbs, fat)
		VALUES (?, ?, ?, ?, ?, ?);
	`

	for _, item := range meal.Items {
		_, err = h.DB.Exec(query,
			id,
			item.Name,
			item.Calories,
			item.Protein,
			item.Carbs,
			item.Fat,
		)
		if err != nil {
			return err
		}
	}

	return nil
}

// @Summary Get user favorite_meals
// @Tags nutrition
// @Security BearerAuth
// @Success 200 {array} Meal
// @Router /nutrition/favorite_meals [get]
func (h *Handler) getUserFavoriteMeals(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	rows, err := h.DB.Query("SELECT * FROM favorite_meals WHERE user_id = ?", userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "failed to fetch favorite meals", err)
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

// @Summary Create a favorite meal
// @Tags nutrition
// @Security BearerAuth
// @Param request body Meal true "Meal data"
// @Success 201 {object} Meal
// @Router /nutrition/meals [post]
func (h *Handler) addFavoriteMeal(w http.ResponseWriter, r *http.Request) {
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
		INSERT INTO favorite_meals (user_id, date, meal_type, time, total_calories)
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
		api.WriteError(w, http.StatusInternalServerError, "failed to insert favorite meal", err)
		return
	}

	api.WriteSuccess(w, http.StatusCreated, map[string]string{"message": "Meal added successfully"})
}

// @Summary Get favorite-meal by ID
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Favorite-Meal ID"
// @Success 200 {object} Meal
// @Router /nutrition/meals/{id} [get]
func (h *Handler) getFavoriteMeal(w http.ResponseWriter, r *http.Request) {
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

	meal, err := getFavoriteMealHelper(h, meal_id, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error fetching favorite meal", err)
		return
	}

	api.WriteSuccess(w, http.StatusOK, meal)
}

// @Summary Update favorite meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param request body Meal true "Meal data"
// @Success 200 {object} Meal
// @Router /nutrition/meals/{id} [put]
func (h *Handler) updateFavoriteMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	mealID, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid favorite_meal ID", err)
		return
	}

	var meal Meal
	if err := json.NewDecoder(r.Body).Decode(&meal); err != nil {
		api.WriteError(w, http.StatusBadRequest, "invalid JSON", err)
		return
	}

	query := `UPDATE favorite_meals SET date = ?, meal_type = ?, time = ?, total_calories = ? WHERE id = ? AND user_id = ?`
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

// @Summary Delete favorite meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Favorite-Meal ID"
// @Success 204 "No Content"
// @Router /nutrition/meals/{id} [delete]
func (h *Handler) deleteFavoriteMeal(w http.ResponseWriter, r *http.Request) {

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

	query := `DELETE FROM favorite_meals WHERE meal_id = ? AND user_id = ?`

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
