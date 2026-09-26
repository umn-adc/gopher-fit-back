package nutrition

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strings"
	"testing"

	"gopherfit/internal/testutil"
)

const updatedItemJSON = `{"id":999,"meal_id":999,"name":"Rice","calories":200,"protein":4,"carbs":44,"fat":1}`

func TestUpdateMealItemOwnershipAndValidation(t *testing.T) {
	tests := []struct {
		name, path, body string
		userID, status   int
	}{
		{"owned item", "/nutrition/meals/10/items/100", updatedItemJSON, 1, 200},
		{"zero nutrition", "/nutrition/meals/10/items/100", `{"name":"Water","calories":0,"protein":0,"carbs":0,"fat":0}`, 1, 200},
		{"other owner's item", "/nutrition/meals/20/items/200", updatedItemJSON, 1, 404},
		{"mismatched parent", "/nutrition/meals/10/items/200", updatedItemJSON, 1, 404},
		{"another owned parent", "/nutrition/meals/11/items/100", updatedItemJSON, 1, 404},
		{"missing meal", "/nutrition/meals/99/items/100", updatedItemJSON, 1, 404},
		{"missing item", "/nutrition/meals/10/items/999", updatedItemJSON, 1, 404},
		{"unauthenticated", "/nutrition/meals/10/items/100", updatedItemJSON, 0, 401},
		{"invalid meal ID", "/nutrition/meals/no/items/100", updatedItemJSON, 1, 400},
		{"zero meal ID", "/nutrition/meals/0/items/100", updatedItemJSON, 1, 400},
		{"negative meal ID", "/nutrition/meals/-1/items/100", updatedItemJSON, 1, 400},
		{"invalid item ID", "/nutrition/meals/10/items/no", updatedItemJSON, 1, 400},
		{"zero item ID", "/nutrition/meals/10/items/0", updatedItemJSON, 1, 400},
		{"negative item ID", "/nutrition/meals/10/items/-1", updatedItemJSON, 1, 400},
		{"overflowing ID", "/nutrition/meals/10/items/999999999999999999999", updatedItemJSON, 1, 400},
		{"missing name", "/nutrition/meals/10/items/100", `{"calories":10}`, 1, 400},
		{"blank name", "/nutrition/meals/10/items/100", `{"name":" \t "}`, 1, 400},
		{"negative calories", "/nutrition/meals/10/items/100", `{"name":"Rice","calories":-1}`, 1, 400},
		{"negative protein", "/nutrition/meals/10/items/100", `{"name":"Rice","protein":-1}`, 1, 400},
		{"negative carbs", "/nutrition/meals/10/items/100", `{"name":"Rice","carbs":-1}`, 1, 400},
		{"negative fat", "/nutrition/meals/10/items/100", `{"name":"Rice","fat":-1}`, 1, 400},
		{"fractional nutrition", "/nutrition/meals/10/items/100", `{"name":"Rice","fat":1.5}`, 1, 400},
		{"wrong type", "/nutrition/meals/10/items/100", `{"name":"Rice","fat":"1"}`, 1, 400},
		{"malformed JSON", "/nutrition/meals/10/items/100", `{`, 1, 400},
		{"multiple values", "/nutrition/meals/10/items/100", updatedItemJSON + `{}`, 1, 400},
		{"null", "/nutrition/meals/10/items/100", `null`, 1, 400},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			conn, client := mealItemFixture(t)
			before := readMealItem(t, conn, 100)
			otherBefore := readMealItem(t, conn, 200)
			res := client.Request(t, tt.userID, http.MethodPut, tt.path, tt.body)
			testutil.AssertStatus(t, res, tt.status)
			after := readMealItem(t, conn, 100)
			if tt.status == 200 {
				var want, response MealItem
				if err := json.Unmarshal([]byte(tt.body), &want); err != nil {
					t.Fatal(err)
				}
				want.ID, want.MealID = 100, 10
				if err := json.Unmarshal(res.Body.Bytes(), &response); err != nil {
					t.Fatal(err)
				}
				if response != want || after != want {
					t.Fatalf("response=%+v, stored=%+v, want=%+v", response, after, want)
				}
			} else if after != before {
				t.Fatalf("rejected update changed item: %+v -> %+v", before, after)
			}
			if got := readMealItem(t, conn, 200); got != otherBefore {
				t.Fatalf("changed other user's item: %+v", got)
			}
		})
	}
}

func TestUpdateMealItemDatabaseFailure(t *testing.T) {
	conn, client := mealItemFixture(t)
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
	res := client.Request(t, 1, http.MethodPut, "/nutrition/meals/10/items/100", updatedItemJSON)
	testutil.AssertStatus(t, res, 500)
	if strings.Contains(res.Body.String(), "database is closed") {
		t.Fatal("internal database error leaked to client")
	}
}

func mealItemFixture(t *testing.T) (*sql.DB, *testutil.Client) {
	t.Helper()
	conn := testutil.NewDB(t)
	testutil.Exec(t, conn, `
		INSERT INTO users (id, username, password) VALUES (1, 'one', X'01'), (2, 'two', X'02');
		INSERT INTO meals (id, user_id, date, meal_type) VALUES
			(10, 1, '2026-09-21', 'Lunch'), (11, 1, '2026-09-21', 'Dinner'), (20, 2, '2026-09-21', 'Lunch');
		INSERT INTO meal_items (id, meal_id, name, calories, protein, carbs, fat) VALUES
			(100, 10, 'Original', 100, 10, 10, 1), (200, 20, 'Private', 200, 20, 20, 2);
	`)
	return conn, testutil.NewClient(t, NewHandler(conn).RegisterRoutes())
}

func readMealItem(t *testing.T, conn *sql.DB, id int) MealItem {
	t.Helper()
	var item MealItem
	if err := conn.QueryRow(`SELECT id, meal_id, name, calories, protein, carbs, fat FROM meal_items WHERE id = ?`, id).
		Scan(&item.ID, &item.MealID, &item.Name, &item.Calories, &item.Protein, &item.Carbs, &item.Fat); err != nil {
		t.Fatal(err)
	}
	return item
}
