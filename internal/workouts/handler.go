package workouts

import "net/http"

func Register(mux *http.ServeMux) {
	mux.HandleFunc("/workouts", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("Workouts endpoint"))
	})
}
