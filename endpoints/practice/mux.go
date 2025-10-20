package practice

import "net/http"

func GetServeMux() *http.ServeMux {
	mux := http.NewServeMux()

	// SET UP YOUR ENDPOINTS HERE
	// mux.HandleFunc("GET /practice/some_endpoint", yourFunction)
	mux.HandleFunc("GET /practice/teerark", handleTeerark)

	return mux
}
