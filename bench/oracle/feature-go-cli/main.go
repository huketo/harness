// Command logsum summarizes synthetic application logs.
package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"

	"example.com/logsum/internal/format"
	"example.com/logsum/internal/parse"
	"example.com/logsum/internal/summary"
)

const usage = "usage: logsum levels <logfile> | logsum top [-n rows] [-format text|json|csv] <logfile>"

const defaultTopRows = 5

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, usage)
		return 1
	}
	switch args[0] {
	case "levels":
		return runLevels(args[1:], stdout, stderr)
	case "top":
		return runTop(args[1:], stdout, stderr)
	default:
		fmt.Fprintf(stderr, "unknown subcommand %q\n%s\n", args[0], usage)
		return 1
	}
}

func runLevels(args []string, stdout, stderr io.Writer) int {
	if len(args) != 1 {
		fmt.Fprintln(stderr, "levels takes exactly one log file")
		return 1
	}
	records, code := load(args[0], stderr)
	if code != 0 {
		return code
	}
	if err := summary.WriteLevels(stdout, summary.ByLevel(records)); err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	return 0
}

func runTop(args []string, stdout, stderr io.Writer) int {
	flags := flag.NewFlagSet("top", flag.ContinueOnError)
	flags.SetOutput(stderr)
	rows := flags.Int("n", defaultTopRows, "number of components to report; 0 reports every component")
	formatName := flags.String("format", "text", "output format: text, json or csv")
	if err := flags.Parse(args); err != nil {
		return 1
	}
	if flags.NArg() != 1 {
		fmt.Fprintln(stderr, "top takes exactly one log file")
		return 1
	}
	records, code := load(flags.Arg(0), stderr)
	if code != 0 {
		return code
	}
	if err := format.Components(stdout, summary.Top(records, *rows), *formatName); err != nil {
		fmt.Fprintln(stderr, err)
		if errors.Is(err, format.ErrUnknown) {
			return 2
		}
		return 1
	}
	return 0
}

// load reads records and maps failures to an exit code: malformed input is 2,
// anything else is 1.
func load(path string, stderr io.Writer) ([]parse.Record, int) {
	records, err := readRecords(path)
	if err == nil {
		return records, 0
	}
	fmt.Fprintln(stderr, err)
	if errors.Is(err, parse.ErrMalformed) {
		return nil, 2
	}
	return nil, 1
}

func readRecords(path string) ([]parse.Record, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	return parse.Reader(file)
}
