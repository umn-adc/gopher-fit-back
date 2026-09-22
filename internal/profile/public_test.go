package profile

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"reflect"
	"testing"

	"gopherfit/internal/testutil"
)

func TestPublicProfileLookup(t *testing.T) {
	tests := []struct {
		name, path     string
		userID, status int
	}{
		{"another user", "/profile/2", 1, 200},
		{"own username", "/profile/1", 1, 200},
		{"user without private profile", "/profile/3", 1, 200},
		{"no authentication", "/profile/2", 0, 401},
		{"noninteger", "/profile/no", 1, 400},
		{"negative", "/profile/-2", 1, 400},
		{"zero", "/profile/0", 1, 400},
		{"overflow", "/profile/99999999999999999999", 1, 400},
		{"missing user", "/profile/999", 1, 404},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, client := profileFixture(t)
			res := client.Request(t, tt.userID, http.MethodGet, tt.path, "")
			testutil.AssertStatus(t, res, tt.status)
			if tt.status == 200 {
				var fields map[string]any
				if err := json.Unmarshal(res.Body.Bytes(), &fields); err != nil {
					t.Fatal(err)
				}
				expected := map[string]map[string]any{
					"/profile/1": {"user_id": float64(1), "username": "caller"},
					"/profile/2": {"user_id": float64(2), "username": "target"},
					"/profile/3": {"user_id": float64(3), "username": "no-profile"},
				}
				if !reflect.DeepEqual(fields, expected[tt.path]) {
					t.Fatalf("public fields = %v, want exactly %v", fields, expected[tt.path])
				}
			}
		})
	}
}

func TestPrivateProfileRouteStillReturnsOnlyCaller(t *testing.T) {
	_, client := profileFixture(t)
	res := client.Request(t, 1, http.MethodGet, "/profile/", "")
	testutil.AssertStatus(t, res, 200)
	var profile Profile
	if err := json.Unmarshal(res.Body.Bytes(), &profile); err != nil {
		t.Fatal(err)
	}
	if profile.UserID != 1 || profile.Name != "Caller Private" || profile.Weight != 70 || len(profile.Goals) != 1 {
		t.Fatalf("private profile changed: %+v", profile)
	}
	res = client.Request(t, 0, http.MethodGet, "/profile/", "")
	testutil.AssertStatus(t, res, 401)
}

func TestPublicProfileReturnsUpdatedUsername(t *testing.T) {
	_, client := profileFixture(t)
	res := client.Request(t, 2, http.MethodPut, "/profile/username", `{"username":"renamed"}`)
	testutil.AssertStatus(t, res, 200)
	res = client.Request(t, 1, http.MethodGet, "/profile/2", "")
	testutil.AssertStatus(t, res, 200)
	var public PublicProfile
	if err := json.Unmarshal(res.Body.Bytes(), &public); err != nil {
		t.Fatal(err)
	}
	if public.UserID != 2 || public.Username != "renamed" {
		t.Fatalf("public profile = %+v", public)
	}
}

func TestPublicProfileDatabaseFailure(t *testing.T) {
	conn, client := profileFixture(t)
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
	testutil.AssertStatus(t, client.Request(t, 1, http.MethodGet, "/profile/2", ""), 500)
}

func profileFixture(t *testing.T) (*sql.DB, *testutil.Client) {
	t.Helper()
	conn := testutil.NewDB(t)
	testutil.Exec(t, conn, `
		INSERT INTO users (id, username, password) VALUES
			(1, 'caller', X'0123'), (2, 'target', X'4567'), (3, 'no-profile', X'89');
		INSERT INTO profiles (user_id, name, age, height, weight, gender, activity_level, goals, sports) VALUES
			(1, 'Caller Private', 21, 170, 70, 'Other', 'Sedentary', '["private goal"]', '["private sport"]'),
			(2, 'Target Private', 22, 180, 80, 'Other', 'Very Active', '["secret goal"]', '["secret sport"]');
	`)
	return conn, testutil.NewClient(t, NewHandler(conn).RegisterRoutes())
}
