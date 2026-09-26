package social

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"net/url"
	"reflect"
	"testing"

	"gopherfit/internal/profile"
	"gopherfit/internal/testutil"
	"gopherfit/internal/workouts"
)

func TestLeaderboardUsesDenseRanksAndTieInclusivePercentiles(t *testing.T) {
	_, client := leaderboardFixture(t)
	for user, weights := range map[int][]float64{1: {300}, 2: {200, 90}, 3: {200}, 4: {100}, 5: {0}} {
		for _, weight := range weights {
			logRankWorkout(t, client, user, " Bench\tPress ", weight)
		}
	}
	logRankWorkout(t, client, 2, "Squat", 999)
	res := client.Request(t, 6, "GET", "/social/leaderboard?exercise="+url.QueryEscape(" \tBENCH\u00a0PRESS "), "")
	testutil.AssertStatus(t, res, 200)
	var got []LeaderboardEntry
	if err := json.Unmarshal(res.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	want := []LeaderboardEntry{
		{UserID: 1, Username: "user1", MaxWeight: 300, Rank: 1, Percentile: 100},
		{UserID: 2, Username: "user2", MaxWeight: 200, Rank: 2, Percentile: 75},
		{UserID: 3, Username: "user3", MaxWeight: 200, Rank: 2, Percentile: 75},
		{UserID: 4, Username: "user4", MaxWeight: 100, Rank: 3, Percentile: 25},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("leaderboard=%+v, want=%+v", got, want)
	}
	var fields []map[string]any
	if err := json.Unmarshal(res.Body.Bytes(), &fields); err != nil {
		t.Fatal(err)
	}
	for _, entry := range fields {
		if len(entry) != 5 {
			t.Fatalf("unexpected public leaderboard fields: %v", entry)
		}
		for _, key := range []string{"user_id", "username", "max_weight", "rank", "percentile"} {
			if _, ok := entry[key]; !ok {
				t.Fatalf("missing %s", key)
			}
		}
	}
	// No cached username or static fixture data: a profile rename is visible.
	testutil.AssertStatus(t, client.Request(t, 2, "PUT", "/profile/username", `{"username":"renamed"}`), 200)
	res = client.Request(t, 1, "GET", "/social/leaderboard?exercise=bench+press", "")
	testutil.AssertStatus(t, res, 200)
	if err := json.Unmarshal(res.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got[1].Username != "renamed" {
		t.Fatalf("stale leaderboard username: %+v", got[1])
	}

	res = client.Request(t, 1, "GET", "/social/leaderboard?exercise=Squat", "")
	testutil.AssertStatus(t, res, 200)
	if err := json.Unmarshal(res.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].UserID != 2 || got[0].Rank != 1 || got[0].Percentile != 100 {
		t.Fatalf("single participant: %+v", got)
	}
}

func TestMuscleRanksUseGlobalPopulationButExposeOnlyCaller(t *testing.T) {
	_, client := leaderboardFixture(t)
	logRankWorkout(t, client, 1, "Bench Press", 300)
	bench := logRankWorkout(t, client, 2, "  Bench   Press  ", 200)
	logRankWorkout(t, client, 3, "bench press", 100)
	squat := logRankWorkout(t, client, 2, "Squat", 150)
	res := client.Request(t, 2, "GET", "/social/muscle-ranks?user_id=1", "")
	testutil.AssertStatus(t, res, 200)
	var got []MuscleRank
	if err := json.Unmarshal(res.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("ranks=%+v", got)
	}
	if got[0].UserID != 2 || got[0].ExerciseKey != "bench press" || got[0].ExerciseName != "Bench Press" || got[0].SourceWorkoutItemID != bench.Items[0].ID || got[0].MaxWeight != 200 || got[0].Rank != 2 || math.Abs(got[0].Percentile-200.0/3) > 1e-9 {
		t.Fatalf("bench rank=%+v", got[0])
	}
	if got[1].UserID != 2 || got[1].ExerciseKey != "squat" || got[1].SourceWorkoutItemID != squat.Items[0].ID || got[1].Rank != 1 || got[1].Percentile != 100 {
		t.Fatalf("squat rank=%+v", got[1])
	}
	res = client.Request(t, 6, "GET", "/social/muscle-ranks", "")
	testutil.AssertStatus(t, res, 200)
	if res.Body.String() != "[]\n" {
		t.Fatalf("empty records=%s", res.Body.String())
	}
}

func TestRanksChangeAfterEditAndParentDeletion(t *testing.T) {
	_, client := leaderboardFixture(t)
	first := logRankWorkout(t, client, 1, "Bench Press", 100)
	logRankWorkout(t, client, 2, "Bench Press", 200)
	res := client.Request(t, 1, "PUT", fmt.Sprintf("/workouts/%d/items/%d", first.ID, first.Items[0].ID), `{"exercise_name":"Bench Press","weight":300}`)
	testutil.AssertStatus(t, res, 204)
	res = client.Request(t, 2, "GET", "/social/muscle-ranks", "")
	testutil.AssertStatus(t, res, 200)
	var ranks []MuscleRank
	if err := json.Unmarshal(res.Body.Bytes(), &ranks); err != nil {
		t.Fatal(err)
	}
	if len(ranks) != 1 || ranks[0].Rank != 2 || ranks[0].Percentile != 50 {
		t.Fatalf("ranks after edit=%+v", ranks)
	}
	testutil.AssertStatus(t, client.Request(t, 1, "DELETE", fmt.Sprintf("/workouts/%d", first.ID), ""), 204)
	res = client.Request(t, 2, "GET", "/social/muscle-ranks", "")
	testutil.AssertStatus(t, res, 200)
	if err := json.Unmarshal(res.Body.Bytes(), &ranks); err != nil {
		t.Fatal(err)
	}
	if len(ranks) != 1 || ranks[0].Rank != 1 || ranks[0].Percentile != 100 {
		t.Fatalf("ranks after deletion=%+v", ranks)
	}
}

func TestRankingEndpointsValidationAndEmptyResults(t *testing.T) {
	_, client := leaderboardFixture(t)
	for _, tt := range []struct {
		path           string
		userID, status int
	}{
		{"/social/leaderboard", 1, 400},
		{"/social/leaderboard?exercise=", 1, 400},
		{"/social/leaderboard?exercise=%20%09%20", 1, 400},
		{"/social/leaderboard?exercise=Squat", 0, 401},
		{"/social/muscle-ranks", 0, 401},
		{"/social/leaderboard?exercise=Unknown", 1, 200},
		{"/social/leaderboard?exercise=" + url.QueryEscape("' OR 1=1 --"), 1, 200},
		{"/social/muscle-ranks", 1, 200},
	} {
		t.Run(fmt.Sprintf("%s user=%d", tt.path, tt.userID), func(t *testing.T) {
			res := client.Request(t, tt.userID, "GET", tt.path, "")
			testutil.AssertStatus(t, res, tt.status)
			if tt.status == 200 && res.Body.String() != "[]\n" {
				t.Fatalf("expected [], got %s", res.Body.String())
			}
		})
	}
}

func TestRankingDatabaseErrorsReturnJSON(t *testing.T) {
	conn, client := leaderboardFixture(t)
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
	for _, path := range []string{"/social/leaderboard?exercise=Squat", "/social/muscle-ranks"} {
		testutil.AssertStatus(t, client.Request(t, 1, "GET", path, ""), 500)
	}
}

func leaderboardFixture(t *testing.T) (*sql.DB, *testutil.Client) {
	t.Helper()
	conn := testutil.NewDB(t)
	for userID := 1; userID <= 6; userID++ {
		testutil.Exec(t, conn, `INSERT INTO users (id, username, password) VALUES (?, ?, ?)`, userID, fmt.Sprintf("user%d", userID), []byte("hash"))
	}
	mux := http.NewServeMux()
	mux.Handle("/social/", NewHandler(conn).RegisterRoutes())
	mux.Handle("/workouts/", workouts.NewHandler(conn).RegisterRoutes())
	mux.Handle("/profile/", profile.NewHandler(conn).RegisterRoutes())
	return conn, testutil.NewClient(t, mux)
}

func logRankWorkout(t *testing.T, client *testutil.Client, userID int, name string, weight float64) workouts.Workout {
	t.Helper()
	body, err := json.Marshal(workouts.Workout{WorkoutName: "Ranking", Items: []workouts.WorkoutItem{{ExerciseName: name, Weight: weight}}})
	if err != nil {
		t.Fatal(err)
	}
	res := client.Request(t, userID, "POST", "/workouts/", string(body))
	testutil.AssertStatus(t, res, 201)
	var w workouts.Workout
	if err := json.Unmarshal(res.Body.Bytes(), &w); err != nil {
		t.Fatal(err)
	}
	return w
}
