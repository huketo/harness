// Package parse turns raw log lines into structured records.
package parse

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"strings"
)

// ErrMalformed reports a line that does not follow "ts level component message".
var ErrMalformed = errors.New("malformed log line")

var knownLevels = map[string]bool{
	"DEBUG": true,
	"INFO":  true,
	"WARN":  true,
	"ERROR": true,
}

// Record is one parsed log line.
type Record struct {
	Timestamp string
	Level     string
	Component string
	Message   string
}

// Line parses a single log line. The four fields are separated by one space
// each and the message is the remainder of the line.
func Line(line string) (Record, error) {
	trimmed := strings.TrimSpace(line)
	fields := strings.SplitN(trimmed, " ", 4)
	if len(fields) < 4 {
		return Record{}, fmt.Errorf("%w: want 4 fields, got %d", ErrMalformed, len(fields))
	}
	if !knownLevels[fields[1]] {
		return Record{}, fmt.Errorf("%w: unknown level %q", ErrMalformed, fields[1])
	}
	if fields[0] == "" || fields[2] == "" {
		return Record{}, fmt.Errorf("%w: empty timestamp or component", ErrMalformed)
	}
	return Record{
		Timestamp: fields[0],
		Level:     fields[1],
		Component: fields[2],
		Message:   strings.TrimSpace(fields[3]),
	}, nil
}

// Reader parses every record in r. Blank lines and lines starting with "#" are
// skipped. The first malformed line aborts the read.
func Reader(r io.Reader) ([]Record, error) {
	scanner := bufio.NewScanner(r)
	records := make([]Record, 0, 16)
	number := 0
	for scanner.Scan() {
		number++
		text := strings.TrimSpace(scanner.Text())
		if text == "" || strings.HasPrefix(text, "#") {
			continue
		}
		record, err := Line(text)
		if err != nil {
			return nil, fmt.Errorf("line %d: %w", number, err)
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return records, nil
}
