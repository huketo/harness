package summary

import (
	"bytes"
	"testing"

	"example.com/logsum/internal/parse"
)

func sample() []parse.Record {
	return []parse.Record{
		{Timestamp: "2024-05-01T00:00:01Z", Level: "INFO", Component: "api", Message: "started"},
		{Timestamp: "2024-05-01T00:00:02Z", Level: "ERROR", Component: "db", Message: "timeout"},
		{Timestamp: "2024-05-01T00:00:03Z", Level: "INFO", Component: "api", Message: "ok"},
		{Timestamp: "2024-05-01T00:00:04Z", Level: "WARN", Component: "cache", Message: "evicted"},
	}
}

func TestByLevelUsesCanonicalOrder(t *testing.T) {
	got := ByLevel(sample())
	want := []LevelCount{
		{Level: "INFO", Count: 2},
		{Level: "WARN", Count: 1},
		{Level: "ERROR", Count: 1},
	}
	if len(got) != len(want) {
		t.Fatalf("ByLevel = %+v, want %+v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("ByLevel[%d] = %+v, want %+v", i, got[i], want[i])
		}
	}
}

func TestByLevelOmitsUnusedLevels(t *testing.T) {
	for _, count := range ByLevel(sample()) {
		if count.Level == "DEBUG" {
			t.Fatalf("ByLevel included DEBUG with no DEBUG records")
		}
	}
}

func TestWriteLevelsRendersOneLinePerRow(t *testing.T) {
	var buf bytes.Buffer
	if err := WriteLevels(&buf, ByLevel(sample())); err != nil {
		t.Fatalf("WriteLevels returned error: %v", err)
	}
	want := "INFO 2\nWARN 1\nERROR 1\n"
	if buf.String() != want {
		t.Fatalf("WriteLevels wrote %q, want %q", buf.String(), want)
	}
}
