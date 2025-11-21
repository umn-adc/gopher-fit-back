package nutrition

type Meal struct {
	ID            int         `json:"id"`
	UserID        int         `json:"user_id"`
	Date          string      `json:"date"`
	MealType      string      `json:"meal_type"` // Breakfast, Lunch, Dinner, Snack
	Time          string      `json:"time"`
	TotalCalories int         `json:"total_calories"`
	Items         []MealItem  `json:"items"`
}

type MealItem struct {
	ID       int    `json:"id"`
	MealID   int    `json:"meal_id"`
	Name     string `json:"name"`
	Calories int    `json:"calories"`
	Protein  int    `json:"protein"`
	Carbs    int    `json:"carbs"`
	Fat      int    `json:"fat"`
}
