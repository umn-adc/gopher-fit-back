package main

import (
	"gopherfit/server/endpoints/example"
	"net/http"
)

func main() {
	baseMux := http.NewServeMux()

	baseMux.HandleFunc("/cool", func(w http.ResponseWriter, r *http.Request) {
		println("Got message at /cool!")
	})

	baseMux.Handle("/example/", example.GetServeMux())

	println("Listening")
	http.ListenAndServe("localhost:3000", baseMux)
}
