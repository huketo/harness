package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"sort"
	"strings"
	"testing"

	"example.com/logsum/internal/format"
	"example.com/logsum/internal/parse"
	"example.com/logsum/internal/summary"
)

func loadSample(t *testing.T) []parse.Record {
	t.Helper()
	file, err := os.Open("testdata/app.txt")
	if err != nil {
		t.Fatalf("open testdata/app.txt: %v", err)
	}
	defer file.Close()
	records, err := parse.Reader(file)
	if err != nil {
		t.Fatalf("parse testdata/app.txt: %v", err)
	}
	if len(records) != 18 {
		t.Fatalf("len(records) = %d, want 18", len(records))
	}
	return records
}

// record builds a record whose only interesting field is the component.
func record(component string) parse.Record {
	return parse.Record{
		Timestamp: "2024-05-01T00:00:00Z",
		Level:     "INFO",
		Component: component,
		Message:   "synthetic",
	}
}

func components(names ...string) []parse.Record {
	records := make([]parse.Record, 0, len(names))
	for _, name := range names {
		records = append(records, record(name))
	}
	return records
}

func assertRows(t *testing.T, label string, got, want []summary.ComponentCount) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("%s = %+v, want %+v", label, got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("%s[%d] = %+v, want %+v (full: %+v)", label, i, got[i], want[i], got)
		}
	}
}

func TestTopOnEmptyInput(t *testing.T) {
	if got := summary.Top(nil, 3); len(got) != 0 {
		t.Fatalf("Top(nil, 3) = %+v, want no rows", got)
	}
	if got := summary.Top([]parse.Record{}, 0); len(got) != 0 {
		t.Fatalf("Top(empty, 0) = %+v, want no rows", got)
	}
}

func TestTopOnSingleComponent(t *testing.T) {
	got := summary.Top(components("other", "other", "other"), 5)
	assertRows(t, "Top(other x3, 5)", got, []summary.ComponentCount{{Component: "other", Count: 3}})
}

func TestTopRanksByCountThenName(t *testing.T) {
	// beta와 alpha는 동률이므로 이름 오름차순, gamma는 건수가 많아 앞에 온다.
	records := components("beta", "alpha", "gamma", "beta", "alpha", "gamma", "gamma")
	want := []summary.ComponentCount{
		{Component: "gamma", Count: 3},
		{Component: "alpha", Count: 2},
		{Component: "beta", Count: 2},
	}
	assertRows(t, "Top(tie sample, 0)", summary.Top(records, 0), want)
	assertRows(t, "Top(tie sample, 2)", summary.Top(records, 2), want[:2])
}

func TestTopRanksSampleLog(t *testing.T) {
	records := loadSample(t)
	full := []summary.ComponentCount{
		{Component: "api", Count: 5},
		{Component: "auth", Count: 4},
		{Component: "cache", Count: 3},
		{Component: "db", Count: 3},
		{Component: "worker", Count: 2},
		{Component: "mailer", Count: 1},
	}
	assertRows(t, "Top(records, 3)", summary.Top(records, 3), full[:3])
	for _, limit := range []int{0, -1} {
		assertRows(t, "Top(records, no limit)", summary.Top(records, limit), full)
	}
	if got := summary.Top(records, 50); len(got) != len(full) {
		t.Fatalf("len(Top(records, 50)) = %d, want %d", len(got), len(full))
	}
}

// assertJSONRows checks the json format without pinning the encoder's output
// byte for byte: one line, one trailing newline, a JSON array, and members that
// carry exactly the keys "component" (string) and "count" (number) in order.
func assertJSONRows(t *testing.T, label, got string, want []summary.ComponentCount) {
	t.Helper()
	if !strings.HasSuffix(got, "\n") {
		t.Fatalf("%s = %q, want a trailing newline", label, got)
	}
	body := strings.TrimSuffix(got, "\n")
	if strings.Contains(body, "\n") {
		t.Fatalf("%s = %q, want a single line", label, got)
	}
	if !strings.HasPrefix(body, "[") || !strings.HasSuffix(body, "]") {
		t.Fatalf("%s = %q, want a JSON array", label, got)
	}
	var rows []map[string]json.RawMessage
	if err := json.Unmarshal([]byte(body), &rows); err != nil {
		t.Fatalf("%s = %q, decode failed: %v", label, got, err)
	}
	if len(rows) != len(want) {
		t.Fatalf("%s = %q, want %d members", label, got, len(want))
	}
	for i, row := range rows {
		keys := make([]string, 0, len(row))
		for key := range row {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		if len(keys) != 2 || keys[0] != "component" || keys[1] != "count" {
			t.Fatalf("%s member %d has keys %v, want exactly component and count", label, i, keys)
		}
		var component string
		if err := json.Unmarshal(row["component"], &component); err != nil {
			t.Fatalf("%s member %d: component is not a JSON string: %v", label, i, err)
		}
		var count int
		if err := json.Unmarshal(row["count"], &count); err != nil {
			t.Fatalf("%s member %d: count is not a JSON number: %v", label, i, err)
		}
		if component != want[i].Component || count != want[i].Count {
			t.Fatalf("%s member %d = {%q, %d}, want {%q, %d}", label, i, component, count, want[i].Component, want[i].Count)
		}
	}
}

func TestFormatComponentsRendersEveryFormat(t *testing.T) {
	counts := summary.Top(loadSample(t), 2)
	want := []summary.ComponentCount{
		{Component: "api", Count: 5},
		{Component: "auth", Count: 4},
	}

	var text bytes.Buffer
	if err := format.Components(&text, counts, "text"); err != nil {
		t.Fatalf("Components(text) returned error: %v", err)
	}
	if text.String() != "api 5\nauth 4\n" {
		t.Fatalf("Components(text) wrote %q", text.String())
	}

	var csv bytes.Buffer
	if err := format.Components(&csv, counts, "csv"); err != nil {
		t.Fatalf("Components(csv) returned error: %v", err)
	}
	if csv.String() != "component,count\napi,5\nauth,4\n" {
		t.Fatalf("Components(csv) wrote %q", csv.String())
	}

	var encoded bytes.Buffer
	if err := format.Components(&encoded, counts, "json"); err != nil {
		t.Fatalf("Components(json) returned error: %v", err)
	}
	assertJSONRows(t, "Components(json)", encoded.String(), want)
}

func TestFormatComponentsRejectsUnknownFormat(t *testing.T) {
	var buf bytes.Buffer
	err := format.Components(&buf, summary.Top(loadSample(t), 2), "yaml")
	if !errors.Is(err, format.ErrUnknown) {
		t.Fatalf("Components(yaml) error = %v, want ErrUnknown", err)
	}
	if buf.Len() != 0 {
		t.Fatalf("Components(yaml) wrote %q, want nothing", buf.String())
	}
}

func TestRunTopDefaultsToFiveRows(t *testing.T) {
	var stdout, stderr bytes.Buffer
	if code := run([]string{"top", "testdata/app.txt"}, &stdout, &stderr); code != 0 {
		t.Fatalf("run(top) = %d, want 0 (stderr: %q)", code, stderr.String())
	}
	want := "api 5\nauth 4\ncache 3\ndb 3\nworker 2\n"
	if stdout.String() != want {
		t.Fatalf("run(top) wrote %q, want %q", stdout.String(), want)
	}
}

func TestRunTopHonoursFlags(t *testing.T) {
	cases := []struct {
		args []string
		want string
	}{
		{[]string{"top", "-n", "2", "testdata/app.txt"}, "api 5\nauth 4\n"},
		{[]string{"top", "-n", "2", "-format", "csv", "testdata/app.txt"}, "component,count\napi,5\nauth,4\n"},
		{[]string{"top", "-n", "1", "-format", "text", "testdata/app.txt"}, "api 5\n"},
	}
	for _, testCase := range cases {
		var stdout, stderr bytes.Buffer
		if code := run(testCase.args, &stdout, &stderr); code != 0 {
			t.Fatalf("run(%v) = %d, want 0 (stderr: %q)", testCase.args, code, stderr.String())
		}
		if stdout.String() != testCase.want {
			t.Fatalf("run(%v) wrote %q, want %q", testCase.args, stdout.String(), testCase.want)
		}
	}

	var stdout, stderr bytes.Buffer
	args := []string{"top", "-format", "json", "-n", "3", "testdata/app.txt"}
	if code := run(args, &stdout, &stderr); code != 0 {
		t.Fatalf("run(%v) = %d, want 0 (stderr: %q)", args, code, stderr.String())
	}
	assertJSONRows(t, "run(top -format json -n 3)", stdout.String(), []summary.ComponentCount{
		{Component: "api", Count: 5},
		{Component: "auth", Count: 4},
		{Component: "cache", Count: 3},
	})
}

func TestRunTopReadsTheGivenFile(t *testing.T) {
	path := t.TempDir() + "/single.txt"
	content := "2024-05-01T00:00:01Z INFO other only record\n"
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write temp log: %v", err)
	}
	var stdout, stderr bytes.Buffer
	if code := run([]string{"top", path}, &stdout, &stderr); code != 0 {
		t.Fatalf("run(top single) = %d, want 0 (stderr: %q)", code, stderr.String())
	}
	if stdout.String() != "other 1\n" {
		t.Fatalf("run(top single) wrote %q, want %q", stdout.String(), "other 1\n")
	}
}

func TestRunTopOnLogWithoutRecords(t *testing.T) {
	path := t.TempDir() + "/empty.txt"
	if err := os.WriteFile(path, []byte("# 주석만 있고 레코드는 없다\n\n"), 0o600); err != nil {
		t.Fatalf("write temp log: %v", err)
	}
	cases := map[string]string{
		"text": "",
		"json": "[]\n",
		"csv":  "component,count\n",
	}
	for formatName, want := range cases {
		t.Run(formatName, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run([]string{"top", "-format", formatName, path}, &stdout, &stderr)
			if code != 0 {
				t.Fatalf("run(top -format %s empty) = %d, want 0 (stderr: %q)", formatName, code, stderr.String())
			}
			if stdout.String() != want {
				t.Fatalf("run(top -format %s empty) wrote %q, want %q", formatName, stdout.String(), want)
			}
		})
	}
}

func TestRunRejectsUnknownFormatWithCodeTwo(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run([]string{"top", "-format", "yaml", "testdata/app.txt"}, &stdout, &stderr)
	if code != 2 {
		t.Fatalf("run(top -format yaml) = %d, want 2", code)
	}
	if stdout.Len() != 0 {
		t.Fatalf("run(top -format yaml) wrote %q to stdout, want nothing", stdout.String())
	}
	if strings.TrimSpace(stderr.String()) == "" {
		t.Fatal("run(top -format yaml) wrote nothing to stderr")
	}
}

func TestRunRejectsMalformedLogWithCodeTwo(t *testing.T) {
	for _, subcommand := range []string{"top", "levels"} {
		var stdout, stderr bytes.Buffer
		code := run([]string{subcommand, "testdata/malformed.txt"}, &stdout, &stderr)
		if code != 2 {
			t.Fatalf("run(%s malformed.txt) = %d, want 2", subcommand, code)
		}
		if strings.TrimSpace(stderr.String()) == "" {
			t.Fatalf("run(%s malformed.txt) wrote nothing to stderr", subcommand)
		}
	}
}

func TestRunMissingFileReturnsOne(t *testing.T) {
	for _, subcommand := range []string{"top", "levels"} {
		var stdout, stderr bytes.Buffer
		if code := run([]string{subcommand, "testdata/absent.txt"}, &stdout, &stderr); code != 1 {
			t.Fatalf("run(%s absent.txt) = %d, want 1", subcommand, code)
		}
	}
}

func TestRunLevelsKeepsTextOutput(t *testing.T) {
	var stdout, stderr bytes.Buffer
	if code := run([]string{"levels", "testdata/app.txt"}, &stdout, &stderr); code != 0 {
		t.Fatalf("run(levels) = %d, want 0 (stderr: %q)", code, stderr.String())
	}
	want := "DEBUG 3\nINFO 8\nWARN 4\nERROR 3\n"
	if stdout.String() != want {
		t.Fatalf("run(levels) wrote %q, want %q", stdout.String(), want)
	}
}

func TestRunRejectsUnknownSubcommand(t *testing.T) {
	var stdout, stderr bytes.Buffer
	if code := run([]string{"histogram", "testdata/app.txt"}, &stdout, &stderr); code != 1 {
		t.Fatalf("run(histogram) = %d, want 1", code)
	}
	if stdout.Len() != 0 {
		t.Fatalf("run(histogram) wrote %q to stdout, want nothing", stdout.String())
	}
}
