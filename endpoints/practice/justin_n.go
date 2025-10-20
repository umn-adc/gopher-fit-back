package practice

import(
	"net/http"
	"fmt"
)

func handleJustin(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	switch name {
		case "":
			http.Error(w, "Name Parameter Required", http.StatusBadRequest)
		case "none":
			http.Error(w, "Name Parameter Required", http.StatusBadRequest)
		default:
			res := fmt.Sprintf("Hello %s from Justin", name)
			w.Write([]byte(res))
	}
}
