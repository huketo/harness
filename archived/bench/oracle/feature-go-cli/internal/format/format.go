// Package format renders aggregated counts in the output formats the CLI
// accepts: text, json and csv.
package format

import (
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strconv"

	"example.com/logsum/internal/summary"
)

// ErrUnknown reports a format name outside text, json and csv.
var ErrUnknown = errors.New("unknown output format")

// Components renders component counts. An unknown format name returns
// ErrUnknown without writing anything.
func Components(w io.Writer, counts []summary.ComponentCount, name string) error {
	switch name {
	case "text":
		return componentsText(w, counts)
	case "json":
		return componentsJSON(w, counts)
	case "csv":
		return componentsCSV(w, counts)
	default:
		return fmt.Errorf("%w: %q (want one of text, json, csv)", ErrUnknown, name)
	}
}

func componentsText(w io.Writer, counts []summary.ComponentCount) error {
	for _, count := range counts {
		if _, err := fmt.Fprintf(w, "%s %d\n", count.Component, count.Count); err != nil {
			return err
		}
	}
	return nil
}

func componentsJSON(w io.Writer, counts []summary.ComponentCount) error {
	rows := counts
	if rows == nil {
		rows = []summary.ComponentCount{}
	}
	return json.NewEncoder(w).Encode(rows)
}

func componentsCSV(w io.Writer, counts []summary.ComponentCount) error {
	writer := csv.NewWriter(w)
	if err := writer.Write([]string{"component", "count"}); err != nil {
		return err
	}
	for _, count := range counts {
		if err := writer.Write([]string{count.Component, strconv.Itoa(count.Count)}); err != nil {
			return err
		}
	}
	writer.Flush()
	return writer.Error()
}
