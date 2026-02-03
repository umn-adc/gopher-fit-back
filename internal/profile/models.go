package profile

type Profile struct {
	UserID        int      `json:"user_id" example:"1"`
	Name          string   `json:"name" example:"John Doe"`
	Age           int      `json:"age" example:"25"`
	Height        int      `json:"height" example:"180"`
	Weight        int      `json:"weight" example:"75"`
	Gender        string   `json:"gender" example:"Male" enums:"Male,Female,Other"`
	ActivityLevel string   `json:"activity_level" example:"Moderately Active" enums:"Sedentary,Lightly Active,Moderately Active,Very Active,Extra Active"`
	Goals         []string `json:"goals" example:"Build Muscle,Lose Weight"`
	Sports        []string `json:"sports" example:"Basketball,Football"`
}
