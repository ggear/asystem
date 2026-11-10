package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"time"
)

type predictor func(inputs map[string][]float64) (map[string][]float64, error)

type manifest struct {
	Flavour   string             `json:"flavour"`
	Model     string             `json:"model"`
	Constants map[string]float64 `json:"constants"`
	Files     map[string]string  `json:"files"`
}

type signature struct {
	Inputs []struct {
		Name       string `json:"name"`
		Parameters struct {
			Required bool `json:"required"`
		} `json:"parameters"`
	} `json:"inputs"`
}

type tensor struct {
	Name string    `json:"name"`
	Data []float64 `json:"data"`
}

type step struct {
	Request struct {
		ID     string   `json:"id"`
		Inputs []tensor `json:"inputs"`
	} `json:"request"`
	Response *struct {
		Outputs []tensor `json:"outputs"`
	} `json:"response"`
	Error string `json:"error"`
}

type bounds struct {
	Absolute float64 `json:"absolute"`
	Relative float64 `json:"relative"`
}

type golden struct {
	Tolerance map[string]bounds `json:"tolerance"`
	Sequences []struct {
		Steps []step `json:"steps"`
	} `json:"sequences"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "ERROR usage consumer <project dir> [<server> <name>]")
		os.Exit(2)
	}
	var served []string
	if len(os.Args) == 4 {
		served = os.Args[2:]
	}
	findings, err := replay(os.Args[1], served)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR %v\n", err)
		os.Exit(1)
	}
	for _, finding := range findings {
		fmt.Fprintf(os.Stderr, "ERROR %s\n", finding)
	}
	if len(findings) > 0 {
		os.Exit(1)
	}
}

func loadProject(dir string) (manifest, signature, string, error) {
	var project manifest
	var sig signature
	if err := readJSON(filepath.Join(dir, "project.json"), &project); err != nil {
		return project, sig, "", err
	}
	signatureBytes, err := os.ReadFile(filepath.Join(dir, "signature.json"))
	if err != nil {
		return project, sig, "", fmt.Errorf("signature unreadable [%w]", err)
	}
	if err := json.Unmarshal(signatureBytes, &sig); err != nil {
		return project, sig, "", fmt.Errorf("signature invalid [%w]", err)
	}
	for path, checksum := range project.Files {
		content, err := os.ReadFile(filepath.Join(dir, path))
		if err != nil {
			return project, sig, "", fmt.Errorf("PJ003 file absent [%s]", path)
		}
		if sum := sha256.Sum256(content); hex.EncodeToString(sum[:]) != checksum {
			return project, sig, "", fmt.Errorf("PJ003 file checksum mismatch [%s]", path)
		}
	}
	if _, evaluated := project.Files["evaluation.json"]; evaluated {
		var verdict struct {
			Passed bool `json:"passed"`
		}
		if err := readJSON(filepath.Join(dir, "evaluation.json"), &verdict); err != nil {
			return project, sig, "", err
		}
		if !verdict.Passed {
			return project, sig, "", fmt.Errorf("acceptance not passed")
		}
	} else if project.Flavour != "static" {
		return project, sig, "", fmt.Errorf("no acceptance evaluation for flavour [%s]", project.Flavour)
	}
	return project, sig, string(signatureBytes), nil
}

func replay(dir string, served []string) ([]string, error) {
	started := time.Now()
	project, sig, signatureJSON, err := loadProject(dir)
	if err != nil {
		return nil, err
	}
	report("verify", fmt.Sprintf("%d files", len(project.Files)+1), started)
	started = time.Now()
	var predict predictor
	loaded := "served"
	if served == nil {
		predict, err = newPredictor(dir, project, signatureJSON)
		loaded = project.Flavour
	} else {
		predict, err = loadServed(fmt.Sprintf("%s/v2/models/%s/infer", served[0], served[1]), signatureJSON)
	}
	if err != nil {
		return nil, err
	}
	report("load", loaded, started)
	started = time.Now()
	steps := 0
	var doc golden
	if err := readJSON(filepath.Join(dir, "golden.json"), &doc); err != nil {
		return nil, err
	}
	var findings []string
	for _, sequence := range doc.Sequences {
		for _, s := range sequence.Steps {
			steps++
			inputs := map[string][]float64{}
			for _, entry := range s.Request.Inputs {
				inputs[entry.Name] = entry.Data
			}
			complete := true
			for _, entry := range sig.Inputs {
				if _, ok := inputs[entry.Name]; entry.Parameters.Required && !ok {
					complete = false
				}
			}
			if s.Error != "" {
				if complete {
					findings = append(findings, fmt.Sprintf("RP001 step [%s] expects a signature error but supplies every required input", s.Request.ID))
				}
				continue
			}
			if !complete {
				findings = append(findings, fmt.Sprintf("RP002 step [%s] is missing required inputs", s.Request.ID))
				continue
			}
			outputs, err := predict(inputs)
			if err != nil {
				findings = append(findings, fmt.Sprintf("RP005 step [%s] the model gave no answer [%v]", s.Request.ID, err))
				continue
			}
			for _, entry := range s.Response.Outputs {
				if !within(outputs[entry.Name], entry.Data, doc.Tolerance, entry.Name) {
					findings = append(findings, fmt.Sprintf("RP003 step [%s] output [%s] is [%v] and the golden is [%v]", s.Request.ID, entry.Name, outputs[entry.Name], entry.Data))
				}
			}
		}
	}
	report("replay", fmt.Sprintf("%d steps", steps), started)
	return findings, nil
}

func report(stage, detail string, started time.Time) {
	fmt.Printf("    %-12s ... done [%s] (%.2fs)\n", stage, detail, time.Since(started).Seconds())
}

func newPredictor(dir string, project manifest, signatureJSON string) (predictor, error) {
	switch project.Flavour {
	case "static":
		constantsJSON, err := json.Marshal(project.Constants)
		if err != nil {
			return nil, fmt.Errorf("constants invalid [%w]", err)
		}
		return loadStatic(string(constantsJSON), signatureJSON)
	case "wasm":
		return loadWasm(filepath.Join(dir, project.Model), signatureJSON)
	case "onnx":
		return loadOnnx(filepath.Join(dir, project.Model), signatureJSON)
	default:
		return nil, fmt.Errorf("no consumer for flavour [%s]", project.Flavour)
	}
}

func within(actual, expected []float64, tolerance map[string]bounds, name string) bool {
	if len(actual) != len(expected) {
		return false
	}
	limit, tolerated := tolerance[name]
	if !tolerated {
		return reflect.DeepEqual(actual, expected)
	}
	for index, value := range actual {
		if math.Abs(value-expected[index]) > limit.Absolute+limit.Relative*math.Abs(expected[index]) {
			return false
		}
	}
	return true
}

func readJSON(path string, target any) error {
	content, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("file unreadable [%s] [%w]", path, err)
	}
	if err := json.Unmarshal(content, target); err != nil {
		return fmt.Errorf("json invalid [%s] [%w]", path, err)
	}
	return nil
}
