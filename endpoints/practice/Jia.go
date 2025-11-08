package practice

import (
	"fmt"
	"net/http"
)

func dontyellplz(w http.ResponseWriter, r *http.Request) {
	Query := r.URL.Query()
	Name := Query.Get("name")
	if Name == "" {
		http.Error(w, "You did not write your name, so you did it wrong", http.StatusBadRequest)
	} else {
		fmt.Fprintf(w, "Hello %s", Name)
	}

}
