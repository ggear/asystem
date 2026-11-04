package main

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"time"

	"github.com/tetratelabs/wazero"
)

const (
	exitUnsupported = 2
	memoryPages     = 16
	callTimeout     = 5 * time.Second
)

type tensor struct {
	Name     string    `json:"name"`
	Datatype string    `json:"datatype"`
	Shape    []int     `json:"shape"`
	Data     []float64 `json:"data"`
}

type signature struct {
	Parameters struct {
		State []json.RawMessage `json:"state"`
	} `json:"parameters"`
	Inputs  []signatureTensor `json:"inputs"`
	Outputs []signatureTensor `json:"outputs"`
}

type signatureTensor struct {
	Name       string `json:"name"`
	Datatype   string `json:"datatype"`
	Shape      []int  `json:"shape"`
	Parameters struct {
		Required bool `json:"required"`
	} `json:"parameters"`
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

type manifest struct {
	Flavor    string             `json:"flavor"`
	Constants map[string]float64 `json:"constants"`
	Files     map[string]struct {
		Path   string `json:"path"`
		Sha256 string `json:"sha256"`
	} `json:"files"`
}

type unsupportedError string

func (e unsupportedError) Error() string { return string(e) }

type predictor func(inputs map[string][]float64) (map[string][]float64, error)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "ERROR usage modelreplay <project dir>")
		os.Exit(exitUnsupported)
	}
	findings, err := replay(os.Args[1])
	var unsupported unsupportedError
	if errors.As(err, &unsupported) {
		fmt.Fprintf(os.Stderr, "SKIP flavor not supported [%s]\n", unsupported)
		os.Exit(exitUnsupported)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR %v\n", err)
		os.Exit(1)
	}
	row, _ := json.Marshal(map[string]any{"host": "go", "arch": architecture(), "passed": len(findings) == 0})
	fmt.Println(string(row))
	for _, finding := range findings {
		fmt.Fprintf(os.Stderr, "ERROR %s\n", finding)
	}
	if len(findings) > 0 {
		os.Exit(1)
	}
}

func replay(projectDir string) ([]string, error) {
	var project manifest
	var sig signature
	var doc golden
	for name, target := range map[string]any{"project.json": &project, "signature.json": &sig, "golden.json": &doc} {
		content, err := os.ReadFile(filepath.Join(projectDir, name))
		if err != nil {
			return nil, fmt.Errorf("file unreadable [%s] [%w]", name, err)
		}
		if err := json.Unmarshal(content, target); err != nil {
			return nil, fmt.Errorf("json invalid [%s] [%w]", name, err)
		}
	}
	var mismatches []string
	for key, entry := range project.Files {
		content, err := os.ReadFile(filepath.Join(projectDir, entry.Path))
		if err != nil {
			mismatches = append(mismatches, fmt.Sprintf("PJ003 file absent [%s]", key))
			continue
		}
		if sum := sha256.Sum256(content); hex.EncodeToString(sum[:]) != entry.Sha256 {
			mismatches = append(mismatches, fmt.Sprintf("PJ003 file checksum mismatch [%s]", key))
		}
	}
	if len(mismatches) > 0 {
		return mismatches, nil
	}
	var predict predictor
	switch project.Flavor {
	case "static":
		predict = func(map[string][]float64) (map[string][]float64, error) {
			outputs := map[string][]float64{}
			for name, value := range project.Constants {
				outputs[name] = []float64{value}
			}
			return outputs, nil
		}
	case "wasm":
		bytes, err := os.ReadFile(filepath.Join(projectDir, project.Files["model"].Path))
		if err != nil {
			return nil, fmt.Errorf("model unreadable [%w]", err)
		}
		predict = func(inputs map[string][]float64) (map[string][]float64, error) {
			return wasmPredict(bytes, sig, inputs)
		}
	default:
		return nil, unsupportedError(project.Flavor)
	}
	var findings []string
	for _, sequence := range doc.Sequences {
		for _, s := range sequence.Steps {
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
				return nil, err
			}
			for _, entry := range s.Response.Outputs {
				if !within(outputs[entry.Name], entry.Data, doc.Tolerance, entry.Name) {
					findings = append(findings, fmt.Sprintf("RP003 step [%s] output [%s] is [%v] and the golden is [%v]", s.Request.ID, entry.Name, outputs[entry.Name], entry.Data))
				}
			}
		}
	}
	return findings, nil
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

func wasmPredict(bytes []byte, sig signature, inputs map[string][]float64) (map[string][]float64, error) {
	stateSlots := len(sig.Parameters.State)
	isState := func(entry signatureTensor) bool { return len(entry.Shape) == 1 && entry.Shape[0] == -1 }
	var row []float64
	for _, entry := range sig.Inputs {
		if isState(entry) {
			continue
		}
		if data := inputs[entry.Name]; len(data) > 0 {
			row = append(row, data[0])
		} else {
			row = append(row, math.NaN())
		}
	}
	for _, entry := range sig.Inputs {
		if !isState(entry) {
			continue
		}
		if data, ok := inputs[entry.Name]; ok {
			row = append(row, data...)
		} else {
			row = append(row, make([]float64, stateSlots)...)
		}
	}
	width := 0
	for _, entry := range sig.Outputs {
		if isState(entry) {
			width += stateSlots
		} else {
			width++
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), callTimeout)
	defer cancel()
	engine := wazero.NewRuntimeWithConfig(ctx, wazero.NewRuntimeConfig().WithMemoryLimitPages(memoryPages).WithCloseOnContextDone(true))
	defer engine.Close(ctx)
	module, err := engine.Instantiate(ctx, bytes)
	if err != nil {
		return nil, fmt.Errorf("module did not instantiate [%w]", err)
	}
	memory := module.Memory()
	predict := module.ExportedFunction("predict")
	if memory == nil || predict == nil {
		return nil, fmt.Errorf("module exports no memory or predict")
	}
	x := make([]byte, len(row)*8)
	for index, value := range row {
		binary.LittleEndian.PutUint64(x[index*8:], math.Float64bits(value))
	}
	if !memory.Write(0, x) {
		return nil, fmt.Errorf("write failed")
	}
	yPtr := uint32(len(x))
	if _, err := predict.Call(ctx, 0, 1, uint64(yPtr)); err != nil {
		return nil, fmt.Errorf("predict failed [%w]", err)
	}
	raw, ok := memory.Read(yPtr, uint32(width*8))
	if !ok {
		return nil, fmt.Errorf("read failed")
	}
	result := map[string][]float64{}
	position := 0
	for _, entry := range sig.Outputs {
		count := 1
		if isState(entry) {
			count = stateSlots
		}
		values := make([]float64, count)
		for index := range values {
			values[index] = math.Float64frombits(binary.LittleEndian.Uint64(raw[(position+index)*8:]))
			if entry.Datatype == "INT64" {
				values[index] = math.Trunc(values[index])
			}
		}
		result[entry.Name] = values
		position += count
	}
	return result, nil
}

func architecture() string {
	switch runtime.GOARCH {
	case "amd64":
		return "x86_64"
	case "arm64":
		return "aarch64"
	}
	return runtime.GOARCH
}
