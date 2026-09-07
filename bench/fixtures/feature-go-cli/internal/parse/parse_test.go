package parse

import (
	"errors"
	"strings"
	"testing"
)

func TestLineParsesFourFields(t *testing.T) {
	record, err := Line("2024-05-01T00:00:01Z INFO api request accepted in 12ms")
	if err != nil {
		t.Fatalf("Line returned error: %v", err)
	}
	want := Record{
		Timestamp: "2024-05-01T00:00:01Z",
		Level:     "INFO",
		Component: "api",
		Message:   "request accepted in 12ms",
	}
	if record != want {
		t.Fatalf("Line = %+v, want %+v", record, want)
	}
}

func TestLineRejectsMalformedInput(t *testing.T) {
	cases := map[string]string{
		"too few fields": "2024-05-01T00:00:01Z INFO api",
		"unknown level":  "2024-05-01T00:00:01Z TRACE api noisy detail",
		"single token":   "not-a-log-line",
	}
	for name, line := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := Line(line); !errors.Is(err, ErrMalformed) {
				t.Fatalf("Line(%q) error = %v, want ErrMalformed", line, err)
			}
		})
	}
}

func TestReaderSkipsBlankAndCommentLines(t *testing.T) {
	input := strings.Join([]string{
		"# synthetic sample",
		"",
		"2024-05-01T00:00:01Z INFO api started",
		"2024-05-01T00:00:02Z WARN db slow query",
		"",
	}, "\n")
	records, err := Reader(strings.NewReader(input))
	if err != nil {
		t.Fatalf("Reader returned error: %v", err)
	}
	if len(records) != 2 {
		t.Fatalf("len(records) = %d, want 2", len(records))
	}
	if records[1].Component != "db" || records[1].Level != "WARN" {
		t.Fatalf("records[1] = %+v, want WARN db", records[1])
	}
}

func TestReaderReportsLineNumber(t *testing.T) {
	input := "2024-05-01T00:00:01Z INFO api started\nbroken line here\n"
	_, err := Reader(strings.NewReader(input))
	if !errors.Is(err, ErrMalformed) {
		t.Fatalf("Reader error = %v, want ErrMalformed", err)
	}
	if !strings.Contains(err.Error(), "line 2") {
		t.Fatalf("Reader error = %q, want it to name line 2", err.Error())
	}
}
