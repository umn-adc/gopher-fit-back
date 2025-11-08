package practice

import "net/http"

func GetServeMux() *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /practice/Bye", dontyellplz)

	// SET UP YOUR ENDPOINTS HERE
	// mux.HandleFunc("GET /practice/some_endpoint", yourFunction)

	return mux
}
