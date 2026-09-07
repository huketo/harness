// Package summary aggregates parsed log records.
package summary

import (
	"fmt"
	"io"
	"sort"

	"example.com/logsum/internal/parse"
)

// levelOrder is the canonical reporting order for severity levels.
var levelOrder = []string{"DEBUG", "INFO", "WARN", "ERROR"}

// LevelCount is the number of records seen for one severity level.
type LevelCount struct {
	Level string `json:"level"`
	Count int    `json:"count"`
}

// ComponentCount is the number of records seen for one component.
type ComponentCount struct {
	Component string `json:"component"`
	Count     int    `json:"count"`
}

// ByLevel counts records per severity level. Levels that never appear are
// omitted and the result follows levelOrder.
func ByLevel(records []parse.Record) []LevelCount {
	counts := make(map[string]int, len(levelOrder))
	for _, record := range records {
		counts[record.Level]++
	}
	result := make([]LevelCount, 0, len(levelOrder))
	for _, level := range levelOrder {
		if counts[level] == 0 {
			continue
		}
		result = append(result, LevelCount{Level: level, Count: counts[level]})
	}
	return result
}

// WriteLevels renders level counts as one "<level> <count>" line per row.
func WriteLevels(w io.Writer, counts []LevelCount) error {
	for _, count := range counts {
		if _, err := fmt.Fprintf(w, "%s %d\n", count.Level, count.Count); err != nil {
			return err
		}
	}
	return nil
}

// Top counts records per component and ranks them by descending count, then by
// ascending component name. A limit of zero or less returns every component.
func Top(records []parse.Record, limit int) []ComponentCount {
	counts := make(map[string]int)
	for _, record := range records {
		counts[record.Component]++
	}
	result := make([]ComponentCount, 0, len(counts))
	for component, count := range counts {
		result = append(result, ComponentCount{Component: component, Count: count})
	}
	sort.Slice(result, func(i, j int) bool {
		if result[i].Count != result[j].Count {
			return result[i].Count > result[j].Count
		}
		return result[i].Component < result[j].Component
	})
	if limit > 0 && limit < len(result) {
		result = result[:limit]
	}
	return result
}
