package social

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"

	"gopherfit/internal/testutil"
)

func TestCreateFriendship(t *testing.T) {
	tests := []struct {
		name, body     string
		userID, status int
		duplicate      bool
	}{
		{"request", `{"user1_id":1,"user2_id":2,"status":"pending"}`, 1, 201, false},
		{"reversed IDs and spoofed actor", `{"user1_id":2,"user2_id":1,"action_user_id":3,"status":"pending"}`, 2, 201, false},
		{"block", `{"user1_id":1,"user2_id":2,"status":"blocked"}`, 1, 201, false},
		{"self", `{"user1_id":1,"user2_id":1,"status":"pending"}`, 1, 400, false},
		{"zero ID", `{"user1_id":1,"user2_id":0,"status":"pending"}`, 1, 400, false},
		{"negative ID", `{"user1_id":-2,"user2_id":1,"status":"pending"}`, 1, 400, false},
		{"not a participant", `{"user1_id":2,"user2_id":3,"status":"pending"}`, 1, 400, false},
		{"missing target", `{"user1_id":1,"user2_id":99,"status":"pending"}`, 1, 404, false},
		{"deleted caller", `{"user1_id":99,"user2_id":2,"status":"pending"}`, 99, 404, false},
		{"initial acceptance", `{"user1_id":1,"user2_id":2,"status":"accepted"}`, 1, 400, false},
		{"unknown status", `{"user1_id":1,"user2_id":2,"status":"friends"}`, 1, 400, false},
		{"missing status", `{"user1_id":1,"user2_id":2}`, 1, 400, false},
		{"malformed JSON", `{`, 1, 400, false},
		{"multiple JSON values", `{"user1_id":1,"user2_id":2,"status":"pending"}{}`, 1, 400, false},
		{"null JSON", `null`, 1, 400, false},
		{"no authentication", `{"user1_id":1,"user2_id":2,"status":"pending"}`, 0, 401, false},
		{"duplicate reverse pair", `{"user1_id":2,"user2_id":1,"status":"blocked"}`, 2, 409, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			conn, client := friendshipFixture(t)
			if tt.duplicate {
				seedFriendship(t, conn, Friendship{1, 2, 1, "pending"})
			}
			res := client.Request(t, tt.userID, http.MethodPost, "/social/friendships", tt.body)
			testutil.AssertStatus(t, res, tt.status)
			var count int
			if err := conn.QueryRow(`SELECT COUNT(*) FROM friendships`).Scan(&count); err != nil {
				t.Fatal(err)
			}
			if tt.status == 201 {
				var payload Friendship
				if err := json.Unmarshal([]byte(tt.body), &payload); err != nil {
					t.Fatal(err)
				}
				want := Friendship{1, 2, tt.userID, payload.Status}
				assertFriendshipResponse(t, res, want)
				if got := readFriendship(t, conn, 1, 2); got != want || count != 1 {
					t.Fatalf("stored=%+v count=%d, want=%+v count=1", got, count, want)
				}
			} else if tt.duplicate {
				if got := readFriendship(t, conn, 1, 2); got != (Friendship{1, 2, 1, "pending"}) || count != 1 {
					t.Fatalf("duplicate changed relationship: %+v, count=%d", got, count)
				}
			} else if count != 0 {
				t.Fatalf("rejected request created %d relationships", count)
			}
		})
	}
}

func TestFriendshipTransitionMatrix(t *testing.T) {
	// The columns are requested statuses: pending, accepted, blocked. Rows
	// distinguish the current action user (outgoing) from the other participant.
	tests := []struct {
		name, current string
		actor         int
		allowed       [3]bool
	}{
		{"outgoing pending", "pending", 1, [3]bool{false, false, true}},
		{"incoming pending", "pending", 2, [3]bool{false, true, true}},
		{"outgoing accepted", "accepted", 1, [3]bool{true, false, true}},
		{"incoming accepted", "accepted", 2, [3]bool{true, false, true}},
		{"outgoing block", "blocked", 1, [3]bool{true, false, false}},
		{"incoming block", "blocked", 2, [3]bool{false, false, false}},
	}
	for _, tt := range tests {
		for i, desired := range []string{"pending", "accepted", "blocked"} {
			t.Run(tt.name+" to "+desired, func(t *testing.T) {
				conn, client := friendshipFixture(t)
				original := Friendship{1, 2, tt.actor, tt.current}
				seedFriendship(t, conn, original)
				// Reversed IDs remain supported, and the body cannot choose the actor.
				body := fmt.Sprintf(`{"user1_id":2,"user2_id":1,"action_user_id":3,"status":%q}`, desired)
				res := client.Request(t, 1, http.MethodPut, "/social/friendships/2", body)
				want, status := original, 400
				if tt.allowed[i] {
					status = 200
					want = Friendship{1, 2, 1, desired}
				}
				testutil.AssertStatus(t, res, status)
				if status == 200 {
					assertFriendshipResponse(t, res, want)
				}
				if got := readFriendship(t, conn, 1, 2); got != want {
					t.Fatalf("stored=%+v, want=%+v", got, want)
				}
			})
		}
	}
}

func TestFriendshipMutationValidation(t *testing.T) {
	tests := []struct {
		name, method, path, body string
		userID, status           int
	}{
		{"change participants", "PUT", "/social/friendships/2", `{"user1_id":1,"user2_id":3,"status":"blocked"}`, 1, 400},
		{"unknown status", "PUT", "/social/friendships/2", `{"user1_id":1,"user2_id":2,"status":"invalid"}`, 1, 400},
		{"missing status", "PUT", "/social/friendships/2", `{"user1_id":1,"user2_id":2}`, 1, 400},
		{"missing pair", "PUT", "/social/friendships/2", `{"status":"blocked"}`, 1, 400},
		{"invalid JSON", "PUT", "/social/friendships/2", `{`, 1, 400},
		{"extra JSON", "PUT", "/social/friendships/2", `{"user1_id":1,"user2_id":2,"status":"blocked"}{}`, 1, 400},
		{"null body", "PUT", "/social/friendships/2", `null`, 1, 400},
		{"unrelated update", "PUT", "/social/friendships/2", `{"user1_id":3,"user2_id":2,"status":"blocked"}`, 3, 404},
		{"unrelated delete", "DELETE", "/social/friendships/2", "", 3, 404},
		{"missing update", "PUT", "/social/friendships/9", `{"user1_id":1,"user2_id":9,"status":"blocked"}`, 1, 404},
		{"missing delete", "DELETE", "/social/friendships/9", "", 1, 404},
	}
	for _, method := range []string{"GET", "PUT", "DELETE"} {
		for _, id := range []string{"no", "0", "-1", "1", "999999999999999999999"} {
			tests = append(tests, struct {
				name, method, path, body string
				userID, status           int
			}{method + " invalid ID " + id, method, "/social/friendships/" + id, `{"user1_id":1,"user2_id":2,"status":"blocked"}`, 1, 400})
		}
		tests = append(tests, struct {
			name, method, path, body string
			userID, status           int
		}{method + " unauthenticated", method, "/social/friendships/2", `{"user1_id":1,"user2_id":2,"status":"blocked"}`, 0, 401})
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			conn, client := friendshipFixture(t)
			want := Friendship{1, 2, 1, "pending"}
			seedFriendship(t, conn, want)
			res := client.Request(t, tt.userID, tt.method, tt.path, tt.body)
			testutil.AssertStatus(t, res, tt.status)
			if got := readFriendship(t, conn, 1, 2); got != want {
				t.Fatalf("rejected mutation changed friendship: %+v", got)
			}
		})
	}
}

func TestDeleteFriendshipAuthorization(t *testing.T) {
	for _, status := range []string{"pending", "accepted", "blocked"} {
		for _, actor := range []int{1, 2} {
			t.Run(fmt.Sprintf("%s actor=%d", status, actor), func(t *testing.T) {
				conn, client := friendshipFixture(t)
				original := Friendship{1, 2, actor, status}
				seedFriendship(t, conn, original)
				res := client.Request(t, 1, http.MethodDelete, "/social/friendships/2", "")
				if status == "blocked" && actor == 2 {
					testutil.AssertStatus(t, res, 400)
					if got := readFriendship(t, conn, 1, 2); got != original {
						t.Fatalf("incoming block changed: %+v", got)
					}
				} else {
					testutil.AssertStatus(t, res, 204)
					var count int
					if err := conn.QueryRow(`SELECT COUNT(*) FROM friendships`).Scan(&count); err != nil {
						t.Fatal(err)
					}
					if count != 0 || res.Body.Len() != 0 {
						t.Fatalf("delete left count=%d, body=%s", count, res.Body.String())
					}
				}
			})
		}
	}
}

func TestFriendshipCollectionsAreScopedToCaller(t *testing.T) {
	conn, client := friendshipFixture(t)
	for _, row := range []Friendship{
		{1, 5, 1, "accepted"}, {5, 6, 5, "accepted"},
		{2, 5, 5, "pending"}, {5, 7, 7, "pending"},
		{3, 5, 3, "blocked"}, {5, 8, 5, "blocked"},
		{1, 2, 1, "accepted"}, {2, 3, 2, "pending"}, {3, 4, 3, "blocked"},
		// Legacy rows can have a nonparticipant action user. They must not leak.
		{1, 3, 5, "pending"}, {1, 4, 5, "blocked"},
	} {
		seedFriendship(t, conn, row)
	}
	tests := []struct {
		path string
		want []int
	}{
		{"/social/friendships", []int{1, 2, 3, 6, 7, 8}},
		{"/social/friendships/accepted", []int{1, 6}},
		{"/social/friendships/outpending", []int{2}},
		{"/social/friendships/inpending", []int{7}},
		{"/social/friendships/outblocks", []int{8}},
		{"/social/friendships/inblocks", []int{3}},
	}
	for _, tt := range tests {
		t.Run(tt.path, func(t *testing.T) {
			res := client.Request(t, 5, http.MethodGet, tt.path, "")
			testutil.AssertStatus(t, res, 200)
			var rows []Friendship
			if err := json.Unmarshal(res.Body.Bytes(), &rows); err != nil {
				t.Fatal(err)
			}
			got := map[int]bool{}
			for _, row := range rows {
				if row.User1ID != 5 && row.User2ID != 5 {
					t.Fatalf("leaked another user's relationship: %+v", row)
				}
				otherID := row.User1ID
				if otherID == 5 {
					otherID = row.User2ID
				}
				got[otherID] = true
			}
			want := map[int]bool{}
			for _, id := range tt.want {
				want[id] = true
			}
			if !reflect.DeepEqual(got, want) || len(rows) != len(want) {
				t.Fatalf("relationships=%+v, want other users=%v", rows, tt.want)
			}
			testutil.AssertStatus(t, client.Request(t, 0, http.MethodGet, tt.path, ""), 401)
			res = client.Request(t, 9, http.MethodGet, tt.path, "")
			testutil.AssertStatus(t, res, 200)
			if res.Body.String() != "[]\n" {
				t.Fatalf("empty collection = %q, want []", res.Body.String())
			}
		})
	}
}

func TestGetFriendshipForEitherParticipant(t *testing.T) {
	conn, client := friendshipFixture(t)
	want := Friendship{1, 2, 1, "pending"}
	seedFriendship(t, conn, want)
	for _, userID := range []int{1, 2} {
		res := client.Request(t, userID, http.MethodGet, fmt.Sprintf("/social/friendships/%d", 3-userID), "")
		testutil.AssertStatus(t, res, 200)
		assertFriendshipResponse(t, res, want)
	}
	testutil.AssertStatus(t, client.Request(t, 3, http.MethodGet, "/social/friendships/2", ""), 404)
}

func TestFriendshipDatabaseFailures(t *testing.T) {
	conn, client := friendshipFixture(t)
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
	for _, method := range []string{"GET", "POST", "PUT", "DELETE"} {
		path := "/social/friendships/2"
		if method == "POST" {
			path = "/social/friendships"
		}
		t.Run(method, func(t *testing.T) {
			res := client.Request(t, 1, method, path, `{"user1_id":1,"user2_id":2,"status":"pending"}`)
			testutil.AssertStatus(t, res, 500)
		})
	}
	for _, suffix := range []string{"", "/accepted", "/outpending", "/inpending", "/outblocks", "/inblocks"} {
		testutil.AssertStatus(t, client.Request(t, 1, "GET", "/social/friendships"+suffix, ""), 500)
	}
}

func TestConcurrentMutationCannotOverwriteSuccessfulBlock(t *testing.T) {
	for _, method := range []string{http.MethodPut, http.MethodDelete} {
		t.Run(method, func(t *testing.T) {
			conn, client := friendshipFixture(t)
			for attempt := 0; attempt < 30; attempt++ {
				testutil.Exec(t, conn, `DELETE FROM friendships`)
				seedFriendship(t, conn, Friendship{1, 2, 1, "pending"})
				start := make(chan struct{})
				blockResult := make(chan *httptest.ResponseRecorder, 1)
				otherResult := make(chan *httptest.ResponseRecorder, 1)
				go func() {
					<-start
					blockResult <- client.Request(t, 1, "PUT", "/social/friendships/2", `{"user1_id":1,"user2_id":2,"status":"blocked"}`)
				}()
				go func() {
					<-start
					otherResult <- client.Request(t, 2, method, "/social/friendships/1", `{"user1_id":1,"user2_id":2,"status":"accepted"}`)
				}()
				close(start)
				block, other := <-blockResult, <-otherResult
				for _, res := range []*httptest.ResponseRecorder{block, other} {
					switch res.Code {
					case 200, 204, 400, 404, 409:
					default:
						t.Fatalf("unexpected concurrent result: status=%d body=%s", res.Code, res.Body.String())
					}
				}
				if block.Code == 200 {
					if got := readFriendship(t, conn, 1, 2); got != (Friendship{1, 2, 1, "blocked"}) {
						t.Fatalf("successful block was overwritten: %+v", got)
					}
				}
			}
		})
	}
}

func friendshipFixture(t *testing.T) (*sql.DB, *testutil.Client) {
	t.Helper()
	conn := testutil.NewDB(t)
	for id := 1; id <= 9; id++ {
		testutil.Exec(t, conn, `INSERT INTO users (id, username, password) VALUES (?, ?, ?)`, id, fmt.Sprintf("user%d", id), []byte("hash"))
	}
	return conn, testutil.NewClient(t, NewHandler(conn).RegisterRoutes())
}

func seedFriendship(t *testing.T, conn *sql.DB, row Friendship) {
	t.Helper()
	testutil.Exec(t, conn, `INSERT INTO friendships (user1_id, user2_id, action_user_id, status) VALUES (?, ?, ?, ?)`, row.User1ID, row.User2ID, row.ActionUserID, row.Status)
}

func readFriendship(t *testing.T, conn *sql.DB, user1, user2 int) Friendship {
	t.Helper()
	var row Friendship
	if err := conn.QueryRow(`SELECT user1_id, user2_id, action_user_id, status FROM friendships WHERE user1_id = ? AND user2_id = ?`, user1, user2).
		Scan(&row.User1ID, &row.User2ID, &row.ActionUserID, &row.Status); err != nil {
		t.Fatal(err)
	}
	return row
}

func assertFriendshipResponse(t *testing.T, res *httptest.ResponseRecorder, want Friendship) {
	t.Helper()
	var got Friendship
	if err := json.Unmarshal(res.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("response=%+v, want=%+v", got, want)
	}
}
