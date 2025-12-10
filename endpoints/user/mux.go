package user

import "net/http"

func GetServeMux() *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /user/helloRStudio", handlergetUser)
	return mux
}
