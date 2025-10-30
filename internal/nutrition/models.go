package nutrition

type Meal struct {
	ID       int    `json:"id"`
	UserID   int    `json:"user_id"`
	Date     string `json:"date"`
	Meal     string `json:"meal"`
	Calories int    `json:"calories"`
	Protein  int    `json:"protein"`
	Carbs    int    `json:"carbs"`
	Fat      int    `json:"fat"`
}