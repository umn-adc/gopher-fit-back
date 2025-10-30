package nutrition

import "net/http"

func Register(mux *http.ServeMux) {
	mux.HandleFunc("/nutrition", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			addMeal(w, r)
		} else {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
}


