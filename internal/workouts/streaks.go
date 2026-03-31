package main

import (
	"fmt"
	"time"
)

type UserStreak struct {
	UserID        string
	CurrentStreak int
	LastCheckInAt time.Time
	LongestStreak int
}

// CheckIn handles when a user logs activity
func (s *UserStreak) CheckIn(now time.Time) {
	// Get start of today and yesterday in UTC
	todayStart := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	yesterdayStart := todayStart.AddDate(0, 0, -1)
	lastCheckInDay := time.Date(
		s.LastCheckInAt.Year(),
		s.LastCheckInAt.Month(),
		s.LastCheckInAt.Day(),
		0, 0, 0, 0,
		time.UTC,
	)

	// If already checked in today, do nothing
	if lastCheckInDay.Equal(todayStart) {
		return
	}

	// If last check-in was yesterday, increment streak
	if lastCheckInDay.Equal(yesterdayStart) {
		s.CurrentStreak++
	} else {
		// Streak broken, reset to 1
		s.CurrentStreak = 1
	}

	// Update last check-in time
	s.LastCheckInAt = now

	// Update longest streak if current is higher
	if s.CurrentStreak > s.LongestStreak {
		s.LongestStreak = s.CurrentStreak
	}
}

// GetStreak returns current streak count
func (s *UserStreak) GetStreak() int {
	// Check if streak is still valid (checked in today or yesterday)
	now := time.Now().UTC()
	todayStart := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	yesterdayStart := todayStart.AddDate(0, 0, -1)
	lastCheckInDay := time.Date(
		s.LastCheckInAt.Year(),
		s.LastCheckInAt.Month(),
		s.LastCheckInAt.Day(),
		0, 0, 0, 0,
		time.UTC,
	)

	// If last check-in was before yesterday, streak is broken
	if lastCheckInDay.Before(yesterdayStart) {
		return 0
	}

	return s.CurrentStreak
}

func main() {
	// Create a new user streak
	streak := UserStreak{
		UserID: "user123",
	}

	// Simulate check-ins
	now := time.Now().UTC()

	fmt.Println("First check-in:")
	streak.CheckIn(now)
	fmt.Println("Current streak:", streak.GetStreak())

	// Simulate next day check-in
	nextDay := now.AddDate(0, 0, 1)
	fmt.Println("\nSecond check-in (next day):")
	streak.CheckIn(nextDay)
	fmt.Println("Current streak:", streak.GetStreak())

	// Simulate missed day (skip one day)
	skipDay := nextDay.AddDate(0, 0, 2)
	fmt.Println("\nCheck-in after missing a day:")
	streak.CheckIn(skipDay)
	fmt.Println("Current streak:", streak.GetStreak())

	fmt.Println("\nLongest streak:", streak.LongestStreak)
}
