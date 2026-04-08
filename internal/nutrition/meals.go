package nutrition

import (
	"encoding/json"
	"gopherfit/internal/api"
	"gopherfit/internal/middleware"
	"net/http"
	"strconv"
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
	// TODO: Implement
}

// @Summary Update meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Param request body Meal true "Meal data"
// @Success 200 {object} Meal
// @Router /nutrition/meals/{id} [put]
func (h *Handler) updateMeal(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}

// @Summary Delete meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Success 204 "No Content"
// @Router /nutrition/meals/{id} [delete]
func (h *Handler) deleteMeal(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement
}

func getMealHelper(h *Handler, id int, userID int) (Meal, error) {
	var meal Meal
	err := h.DB.QueryRow(`SELECT id, user_id, date, meal_type, time, total_calories FROM meals WHERE id = ? AND user_id = ?`, id, userID).
		Scan(&meal.ID, &meal.UserID, &meal.Date, &meal.MealType, &meal.Time, &meal.TotalCalories)

	if err != nil {
		return meal, err
	}

	rows, err := h.DB.Query(`SELECT id, meal_id, name, calories, protein, carbs, fat FROM meal_items WHERE meal_id = ?`, id)
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

// @Summary Favorite a meal
// @Tags nutrition
// @Security BearerAuth
// @Param id path int true "Meal ID"
// @Success 204 "No Content"
// @Router /nutrition/meals/favorite/{id} [delete]
func (h *Handler) favoriteMeal(w http.ResponseWriter, r *http.Request) {
	userID, ok := r.Context().Value(middleware.CtxUserIDKey).(int)
	if !ok {
		api.WriteError(w, http.StatusUnauthorized, "Unauthorized", nil)
		return
	}

	id, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		api.WriteError(w, http.StatusBadRequest, "Invalid meal ID", err)
		return
	}

	meal, err := getMealHelper(h, id, userID)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error fetching workout", err)
		return
	}

	err = addFavMealHelper(h, meal)
	if err != nil {
		api.WriteError(w, http.StatusInternalServerError, "Error writing meal item", err)
		return
	}
}
