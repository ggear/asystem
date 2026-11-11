package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"consumer/runtime"
)

func main() {
	if len(os.Args) < 2 || len(os.Args) == 3 || len(os.Args) > 4 {
		fmt.Fprintln(os.Stderr, "ERROR usage consumer <project dir> [<server> <name>]")
		os.Exit(2)
	}
	var served []string
	if len(os.Args) == 4 {
		served = os.Args[2:]
	}
	findings, err := run(os.Args[1], served)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR [%v]\n", err)
		os.Exit(1)
	}
	for _, finding := range findings {
		fmt.Fprintf(os.Stderr, "ERROR %s [%s]\n", finding.Rule, finding.Message)
	}
	if len(findings) > 0 {
		os.Exit(1)
	}
}

func run(dir string, served []string) ([]runtime.Finding, error) {
	started := time.Now()
	project, err := runtime.ReadProject(dir)
	if err != nil {
		return nil, err
	}
	files, _ := project.Manifest["files"].(map[string]any)
	report("verify", fmt.Sprintf("%d files", len(files)+1), started)
	started = time.Now()
	model, err := runtime.Build(dir, project)
	if err != nil {
		return nil, err
	}
	predict := model.Predict
	loaded := model.Info().Flavour
	if served != nil {
		if predict, err = runtime.LoadServed(fmt.Sprintf("%s/v2/models/%s/infer", served[0], served[1]), project.SignatureJSON); err != nil {
			return nil, &runtime.ModelError{Kind: runtime.KindLoad, Gate: "served", Cause: err.Error()}
		}
		loaded = "served"
	}
	report("load", loaded, started)
	started = time.Now()
	var golden struct {
		Sequences []struct {
			Steps []any `json:"steps"`
		} `json:"sequences"`
	}
	if err := runtime.ReadJSON(filepath.Join(dir, "golden.json"), &golden); err != nil {
		return nil, err
	}
	steps := 0
	for _, sequence := range golden.Sequences {
		steps += len(sequence.Steps)
	}
	findings, err := runtime.Replay(dir, model.Signature(), predict)
	if err != nil {
		return nil, err
	}
	report("replay", fmt.Sprintf("%d steps", steps), started)
	return findings, nil
}

func report(stage, detail string, started time.Time) {
	fmt.Printf("    %-12s ... done [%s] (%.2fs)\n", stage, detail, time.Since(started).Seconds())
}
