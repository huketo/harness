// Command logsum summarizes synthetic application logs.
package main

import (
	"fmt"
	"io"
	"os"

	"example.com/logsum/internal/parse"
	"example.com/logsum/internal/summary"
)

const usage = "usage: logsum levels <logfile>"

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
	records, err := readRecords(args[0])
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	if err := summary.WriteLevels(stdout, summary.ByLevel(records)); err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	return 0
}

func readRecords(path string) ([]parse.Record, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	return parse.Reader(file)
}
