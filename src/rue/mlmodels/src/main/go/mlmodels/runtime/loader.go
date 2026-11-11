package runtime

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"time"

	"github.com/tetratelabs/wazero"
	ort "github.com/yalue/onnxruntime_go"
)

type Tensors = map[string][]float64

type Predict = func(inputs Tensors) (Tensors, error)

type Kind string

const (
	KindLoad      Kind = "Load"
	KindSignature Kind = "Signature"
	KindRuntime   Kind = "Runtime"
	KindVerify    Kind = "Verify"
)

type ModelError struct {
	Kind  Kind
	Gate  string
	Cause string
}

func (e *ModelError) Error() string {
	return fmt.Sprintf("%s %s [%s]", e.Kind, e.Gate, e.Cause)
}

type Info struct {
	Name          string
	Flavour       string
	ContentSha256 string
}

type Finding struct {
	Rule    string
	Message string
}

type Project struct {
	Manifest      map[string]any
	SignatureJSON string
	ContentSha256 string
}

type Model struct {
	info      Info
	signature map[string]any
	directory string
	predict   Predict
}

func Load(directory string) (*Model, error) {
	project, err := ReadProject(directory)
	if err != nil {
		return nil, err
	}
	return Build(directory, project)
}

func ReadProject(directory string) (*Project, error) {
	manifestBytes, err := readBytes(filepath.Join(directory, "project.json"))
	if err != nil {
		return nil, err
	}
	var manifest map[string]any
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return nil, &ModelError{KindLoad, "manifest", fmt.Sprintf("manifest unreadable [%v]", err)}
	}
	files, _ := manifest["files"].(map[string]any)
	for path, checksum := range files {
		content, err := os.ReadFile(filepath.Join(directory, path))
		if err != nil {
			return nil, &ModelError{KindLoad, "PJ003", fmt.Sprintf("file absent [%s]", path)}
		}
		if sum := sha256.Sum256(content); hex.EncodeToString(sum[:]) != text(checksum) {
			return nil, &ModelError{KindLoad, "PJ003", fmt.Sprintf("file checksum mismatch [%s]", path)}
		}
	}
	flavour := text(manifest["flavour"])
	if _, evaluated := files["evaluation.json"]; evaluated {
		var verdict struct {
			Passed bool `json:"passed"`
		}
		if err := ReadJSON(filepath.Join(directory, "evaluation.json"), &verdict); err != nil {
			return nil, err
		}
		if !verdict.Passed {
			return nil, &ModelError{KindLoad, "acceptance", "acceptance not passed"}
		}
	} else if flavour != "static" {
		return nil, &ModelError{KindLoad, "acceptance", fmt.Sprintf("no acceptance evaluation for flavour [%s]", flavour)}
	}
	signatureBytes, err := readBytes(filepath.Join(directory, "signature.json"))
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(manifestBytes)
	return &Project{Manifest: manifest, SignatureJSON: string(signatureBytes), ContentSha256: hex.EncodeToString(sum[:])}, nil
}

func Build(directory string, project *Project) (*Model, error) {
	var signature map[string]any
	if err := json.Unmarshal([]byte(project.SignatureJSON), &signature); err != nil {
		return nil, &ModelError{KindLoad, "signature", fmt.Sprintf("signature invalid [%v]", err)}
	}
	flavour := text(project.Manifest["flavour"])
	model := filepath.Join(directory, text(project.Manifest["model"]))
	var predict Predict
	var err error
	switch flavour {
	case "static":
		var constants []byte
		if constants, err = json.Marshal(project.Manifest["constants"]); err == nil {
			predict, err = loadStatic(string(constants), project.SignatureJSON)
		}
	case "wasm":
		predict, err = loadWasm(model, project.SignatureJSON)
	case "onnx":
		predict, err = loadOnnx(model, project.SignatureJSON)
	default:
		return nil, &ModelError{KindLoad, "flavour", fmt.Sprintf("no loader for flavour [%s]", flavour)}
	}
	if err != nil {
		return nil, &ModelError{KindLoad, "driver", err.Error()}
	}
	return &Model{
		info:      Info{Name: text(project.Manifest["name"]), Flavour: flavour, ContentSha256: project.ContentSha256},
		signature: signature,
		directory: directory,
		predict:   predict,
	}, nil
}

func (m *Model) Info() Info {
	return m.info
}

func (m *Model) Signature() map[string]any {
	return m.signature
}

func (m *Model) Predict(inputs Tensors) (Tensors, error) {
	var missing []string
	for _, entry := range entries(m.signature, "inputs") {
		if name := text(entry["name"]); required(entry) && inputs[name] == nil {
			missing = append(missing, name)
		}
	}
	if len(missing) > 0 {
		return nil, &ModelError{KindSignature, "inputs", fmt.Sprintf("missing required inputs [%v]", missing)}
	}
	slots := 0
	if parameters, ok := m.signature["parameters"].(map[string]any); ok {
		if state, ok := parameters["state"].([]any); ok {
			slots = len(state)
		}
	}
	for _, entry := range entries(m.signature, "inputs") {
		name := text(entry["name"])
		if data, supplied := inputs[name]; supplied && isState(entry) && len(data) != slots {
			return nil, &ModelError{KindSignature, "state", fmt.Sprintf("input [%s] has [%d] values and the signature has [%d] slots", name, len(data), slots)}
		}
	}
	outputs, err := m.predict(inputs)
	if err != nil {
		return nil, &ModelError{KindRuntime, "predict", err.Error()}
	}
	for _, entry := range entries(m.signature, "outputs") {
		if text(entry["datatype"]) != "INT64" {
			continue
		}
		name := text(entry["name"])
		for _, value := range outputs[name] {
			if math.IsNaN(value) || math.IsInf(value, 0) || value != math.Trunc(value) || math.Abs(value) > 1<<53 {
				return nil, &ModelError{KindRuntime, "datatype", fmt.Sprintf("INT64 output [%s] is not an integer [%v]", name, value)}
			}
		}
	}
	return outputs, nil
}

func (m *Model) Verify() error {
	findings, err := Replay(m.directory, m.signature, m.Predict)
	if err != nil {
		return err
	}
	if len(findings) == 0 {
		return nil
	}
	causes := make([]string, len(findings))
	for index, finding := range findings {
		causes[index] = finding.Rule + " " + finding.Message
	}
	return &ModelError{KindVerify, "replay", strings.Join(causes, "; ")}
}

func Replay(directory string, signature map[string]any, predict Predict) ([]Finding, error) {
	var golden struct {
		Tolerance map[string]struct {
			Absolute float64 `json:"absolute"`
			Relative float64 `json:"relative"`
		} `json:"tolerance"`
		Sequences []struct {
			Steps []struct {
				Request struct {
					ID     string `json:"id"`
					Inputs []struct {
						Name string    `json:"name"`
						Data []float64 `json:"data"`
					} `json:"inputs"`
				} `json:"request"`
				Response *struct {
					Outputs []struct {
						Name string    `json:"name"`
						Data []float64 `json:"data"`
					} `json:"outputs"`
				} `json:"response"`
				Error string `json:"error"`
			} `json:"steps"`
		} `json:"sequences"`
	}
	if err := ReadJSON(filepath.Join(directory, "golden.json"), &golden); err != nil {
		return nil, err
	}
	var findings []Finding
	for _, sequence := range golden.Sequences {
		for _, step := range sequence.Steps {
			id := step.Request.ID
			inputs := Tensors{}
			for _, entry := range step.Request.Inputs {
				inputs[entry.Name] = entry.Data
			}
			complete := true
			for _, entry := range entries(signature, "inputs") {
				if _, supplied := inputs[text(entry["name"])]; required(entry) && !supplied {
					complete = false
				}
			}
			if step.Error != "" {
				if complete {
					findings = append(findings, Finding{"RP001", fmt.Sprintf("step [%s] expects a signature error but supplies every required input", id)})
				}
				continue
			}
			if !complete {
				findings = append(findings, Finding{"RP002", fmt.Sprintf("step [%s] is missing required inputs", id)})
				continue
			}
			outputs, err := predict(inputs)
			if err != nil {
				findings = append(findings, Finding{"RP005", fmt.Sprintf("step [%s] the model gave no answer [%v]", id, err)})
				continue
			}
			for _, entry := range step.Response.Outputs {
				limit, tolerated := golden.Tolerance[entry.Name]
				if !within(outputs[entry.Name], entry.Data, limit.Absolute, limit.Relative, tolerated) {
					findings = append(findings, Finding{"RP003", fmt.Sprintf("step [%s] output [%s] is [%v] and the golden is [%v]", id, entry.Name, outputs[entry.Name], entry.Data)})
				}
			}
		}
	}
	return findings, nil
}

func ReadJSON(path string, target any) error {
	content, err := readBytes(path)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(content, target); err != nil {
		return &ModelError{KindLoad, "json", fmt.Sprintf("file unreadable [%s] [%v]", path, err)}
	}
	return nil
}

func readBytes(path string) ([]byte, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, &ModelError{KindLoad, "read", fmt.Sprintf("file unreadable [%s] [%v]", path, err)}
	}
	return content, nil
}

func within(actual, expected []float64, absolute, relative float64, tolerated bool) bool {
	if len(actual) != len(expected) {
		return false
	}
	if !tolerated {
		return reflect.DeepEqual(actual, expected)
	}
	for index, value := range actual {
		if math.Abs(value-expected[index]) > absolute+relative*math.Abs(expected[index]) {
			return false
		}
	}
	return true
}

func entries(signature map[string]any, section string) []map[string]any {
	var found []map[string]any
	items, _ := signature[section].([]any)
	for _, item := range items {
		if entry, ok := item.(map[string]any); ok {
			found = append(found, entry)
		}
	}
	return found
}

func required(entry map[string]any) bool {
	parameters, _ := entry["parameters"].(map[string]any)
	value, _ := parameters["required"].(bool)
	return value
}

func isState(entry map[string]any) bool {
	shape, _ := entry["shape"].([]any)
	return len(shape) == 1 && shape[0] == float64(-1)
}

func text(value any) string {
	content, _ := value.(string)
	return content
}

func loadStatic(constantsJSON string, signatureJSON string) (Predict, error) {
	var constants map[string]float64
	if err := json.Unmarshal([]byte(constantsJSON), &constants); err != nil {
		return nil, fmt.Errorf("constants invalid [%w]", err)
	}
	return func(Tensors) (Tensors, error) {
		outputs := Tensors{}
		for name, value := range constants {
			outputs[name] = []float64{value}
		}
		return outputs, nil
	}, nil
}

func loadWasm(path string, signatureJSON string) (Predict, error) {
	const (
		memoryPages = 16
		callTimeout = 5 * time.Second
		mathModule  = "asystem_math"
	)
	var sig struct {
		Parameters struct {
			State []json.RawMessage `json:"state"`
		} `json:"parameters"`
		Inputs []struct {
			Name  string `json:"name"`
			Shape []int  `json:"shape"`
		} `json:"inputs"`
		Outputs []struct {
			Name     string `json:"name"`
			Datatype string `json:"datatype"`
			Shape    []int  `json:"shape"`
		} `json:"outputs"`
	}
	if err := json.Unmarshal([]byte(signatureJSON), &sig); err != nil {
		return nil, fmt.Errorf("signature invalid [%w]", err)
	}
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("model unreadable [%w]", err)
	}
	ctx := context.Background()
	engine := wazero.NewRuntimeWithConfig(ctx, wazero.NewRuntimeConfig().WithMemoryLimitPages(memoryPages).WithCloseOnContextDone(true))
	maths := engine.NewHostModuleBuilder(mathModule)
	functions := map[string]any{
		"acos": math.Acos, "asin": math.Asin, "atan": math.Atan, "atan2": math.Atan2, "cos": math.Cos, "cosh": math.Cosh, "exp": math.Exp, "log": math.Log,
		"log10": math.Log10, "log2": math.Log2, "pow": math.Pow, "sin": math.Sin, "sinh": math.Sinh, "tan": math.Tan, "tanh": math.Tanh,
	}
	for name, function := range functions {
		maths.NewFunctionBuilder().WithFunc(function).Export(name)
	}
	if _, err := maths.Instantiate(ctx); err != nil {
		return nil, fmt.Errorf("maths functions did not instantiate [%w]", err)
	}
	module, err := engine.CompileModule(ctx, bytes)
	if err != nil {
		return nil, fmt.Errorf("module did not compile [%w]", err)
	}
	return func(inputs Tensors) (Tensors, error) {
		stateSlots := len(sig.Parameters.State)
		isState := func(shape []int) bool { return len(shape) == 1 && shape[0] == -1 }
		var row []float64
		for _, entry := range sig.Inputs {
			if isState(entry.Shape) {
				continue
			}
			if data := inputs[entry.Name]; len(data) > 0 {
				row = append(row, data[0])
			} else {
				row = append(row, math.NaN())
			}
		}
		for _, entry := range sig.Inputs {
			if !isState(entry.Shape) {
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
			if isState(entry.Shape) {
				width += stateSlots
			} else {
				width++
			}
		}
		callCtx, cancel := context.WithTimeout(ctx, callTimeout)
		defer cancel()
		instance, err := engine.InstantiateModule(callCtx, module, wazero.NewModuleConfig().WithName(""))
		if err != nil {
			return nil, fmt.Errorf("module did not instantiate [%w]", err)
		}
		defer instance.Close(callCtx)
		memory := instance.Memory()
		predict := instance.ExportedFunction("predict")
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
		if _, err := predict.Call(callCtx, 0, 1, uint64(yPtr)); err != nil {
			return nil, fmt.Errorf("predict failed [%w]", err)
		}
		raw, ok := memory.Read(yPtr, uint32(width*8))
		if !ok {
			return nil, fmt.Errorf("read failed")
		}
		result := Tensors{}
		position := 0
		for _, entry := range sig.Outputs {
			count := 1
			if isState(entry.Shape) {
				count = stateSlots
			}
			values := make([]float64, count)
			for index := range values {
				values[index] = math.Float64frombits(binary.LittleEndian.Uint64(raw[(position+index)*8:]))
			}
			result[entry.Name] = values
			position += count
		}
		return result, nil
	}, nil
}

func loadOnnx(path string, signatureJSON string) (Predict, error) {
	const exactInteger = 1 << 53
	var sig struct {
		Inputs []struct {
			Name string `json:"name"`
		} `json:"inputs"`
		Outputs []struct {
			Name string `json:"name"`
		} `json:"outputs"`
	}
	if err := json.Unmarshal([]byte(signatureJSON), &sig); err != nil {
		return nil, fmt.Errorf("signature invalid [%w]", err)
	}
	if !ort.IsInitialized() {
		ort.SetSharedLibraryPath(os.Getenv("ONNXRUNTIME_LIB"))
		if err := ort.InitializeEnvironment(); err != nil {
			return nil, fmt.Errorf("onnxruntime unavailable [%w]", err)
		}
	}
	outputNames := make([]string, len(sig.Outputs))
	for index, entry := range sig.Outputs {
		outputNames[index] = entry.Name
	}
	return func(inputs Tensors) (Tensors, error) {
		var inputNames []string
		var feeds []ort.Value
		for _, entry := range sig.Inputs {
			data, supplied := inputs[entry.Name]
			if !supplied {
				continue
			}
			tensor, err := ort.NewTensor(ort.NewShape(1, int64(len(data))), data)
			if err != nil {
				return nil, fmt.Errorf("input invalid [%s] [%w]", entry.Name, err)
			}
			defer tensor.Destroy()
			inputNames = append(inputNames, entry.Name)
			feeds = append(feeds, tensor)
		}
		session, err := ort.NewDynamicAdvancedSession(path, inputNames, outputNames, nil)
		if err != nil {
			return nil, fmt.Errorf("model did not load [%w]", err)
		}
		defer session.Destroy()
		results := make([]ort.Value, len(outputNames))
		if err := session.Run(feeds, results); err != nil {
			return nil, fmt.Errorf("predict failed [%w]", err)
		}
		outputs := Tensors{}
		for index, result := range results {
			var values []float64
			switch tensor := result.(type) {
			case *ort.Tensor[float64]:
				values = append(values, tensor.GetData()...)
			case *ort.Tensor[float32]:
				for _, item := range tensor.GetData() {
					values = append(values, float64(item))
				}
			case *ort.Tensor[int64]:
				for _, item := range tensor.GetData() {
					if item > exactInteger || item < -exactInteger {
						result.Destroy()
						return nil, fmt.Errorf("output out of range [%d]", item)
					}
					values = append(values, float64(item))
				}
			default:
				result.Destroy()
				return nil, fmt.Errorf("output type unsupported [%T]", result)
			}
			result.Destroy()
			outputs[outputNames[index]] = values
		}
		return outputs, nil
	}, nil
}
