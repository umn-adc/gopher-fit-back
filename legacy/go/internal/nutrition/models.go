package nutrition

type Meal struct {
	ID            int        `json:"id" example:"1"`
	UserID        int        `json:"user_id" example:"1"`
	Date          string     `json:"date" example:"2024-01-15"`
	MealType      string     `json:"meal_type" example:"Lunch" enums:"Breakfast,Lunch,Dinner,Snack"`
	Time          string     `json:"time" example:"12:30"`
	TotalCalories int        `json:"total_calories" example:"650"`
	Items         []MealItem `json:"items,omitempty"`
}

type MealItem struct {
	ID       int    `json:"id" example:"1"`
	MealID   int    `json:"meal_id" example:"1"`
	Name     string `json:"name" example:"Grilled Chicken"`
	Calories int    `json:"calories" example:"300"`
	Protein  int    `json:"protein" example:"35"`
	Carbs    int    `json:"carbs" example:"5"`
	Fat      int    `json:"fat" example:"12"`
}

type MacroGoals struct {
	UserID         int `json:"user_id" example:"1"`
	CaloriesTarget int `json:"calories_target" example:"2000"`
	ProteinTarget  int `json:"protein_target" example:"150"`
	CarbsTarget    int `json:"carbs_target" example:"200"`
	FatTarget      int `json:"fat_target" example:"65"`
}
