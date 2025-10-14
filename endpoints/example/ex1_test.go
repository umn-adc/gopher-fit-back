package example

import "testing"

func TestSomething(t *testing.T) {
	if 1 == 3 {
		t.Error("math no longer works")
	}
}
