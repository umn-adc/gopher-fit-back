# Gopher Fit Backend
Welcome to the backend for **Gopher Fit**, a fitness tracking app built with **Go**, and **SQLite**.  

## Setup
Make sure you have these downloaded
- [Go 1.22+](https://go.dev/dl/)
- [Git](https://git-scm.com/)

Then clone this repository into your computer's root folder (recommended)
```
https://github.com/umn-adc/gopher-fit-back
```
Then enter the project folder and open it in your IDE
```
cd gopher-fit-back
code .
```

Once you're in, check your dependencies by running
```
go mod tidy
```

To start the Go server nsure you're in project root, then run
```
go run .
```

You should now see in the terminal:
```
Listening on port: 3000
```
## 📚 Readings
Get a feel for the technologies we’ll be working with!

Before starting any project work, take the Knowledge Quiz below to review key technologies and spot any knowledge gaps: https://forms.gle/32umqmV6hDcfohybA

### 1. REST APIs
Understand how backend services communicate through HTTP requests and JSON.
- [Learn REST APIs (Codecademy)](https://www.codecademy.com/article/what-is-rest) (Read fully)

### 2. Go Basics
Familiarize yourself with Go syntax, types and functions/
- [Learn Go (Official Tour)](https://go.dev/tour) (Read until you are comfortable with basic syntax)

### 3. SQL & SQLite
Learn how relational databases work and how to query data efficiently.
- [What is a relational database?](https://cloud.google.com/learn/what-is-a-relational-database) (Read first 3 sections)
- [Learn SQL / SQLite](https://www.sqlitetutorial.net/) (Read "what is SQLite?", Section 1-3, and Section 9)
- Optional: Download and learn DB Browser to view the project's SQLite database easily https://sqlitebrowser.org/
