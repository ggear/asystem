package runtime

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"math"
	"os"
	"path/filepath"
	"testing"
)

func project(t *testing.T, value float64, datatype string, goldenOut float64) string {
	t.Helper()
	directory := t.TempDir()
	signature, _ := json.Marshal(map[string]any{
		"name":       "demo_calc",
		"inputs":     []any{map[string]any{"name": "demo_in", "datatype": "FP64", "shape": []int{1}, "parameters": map[string]any{"required": true}}},
		"outputs":    []any{map[string]any{"name": "demo_out", "datatype": datatype, "shape": []int{1}, "parameters": map[string]any{"required": true}}},
		"parameters": map[string]any{},
	})
	golden, _ := json.Marshal(map[string]any{"sequences": []any{map[string]any{"steps": []any{map[string]any{
		"request":  map[string]any{"id": "one", "inputs": []any{map[string]any{"name": "demo_in", "data": []float64{1}}}},
		"response": map[string]any{"outputs": []any{map[string]any{"name": "demo_out", "data": []float64{goldenOut}}}},
	}}}}})
	files := map[string]string{}
	for name, content := range map[string][]byte{"signature.json": signature, "golden.json": golden} {
		if err := os.WriteFile(filepath.Join(directory, name), content, 0o600); err != nil {
			t.Fatal(err)
		}
		sum := sha256.Sum256(content)
		files[name] = hex.EncodeToString(sum[:])
	}
	manifest, _ := json.Marshal(map[string]any{"name": "demo_calc", "flavour": "static", "constants": map[string]float64{"demo_out": value}, "files": files})
	if err := os.WriteFile(filepath.Join(directory, "project.json"), manifest, 0o600); err != nil {
		t.Fatal(err)
	}
	return directory
}

func kindOf(err error) Kind {
	if modelError, ok := errors.AsType[*ModelError](err); ok {
		return modelError.Kind
	}
	return ""
}

func TestLoader_LoadsPredictsAndVerifies(t *testing.T) {
	model, err := Load(project(t, 3, "FP64", 3))
	if err != nil {
		t.Fatal(err)
	}
	if err := model.Verify(); err != nil {
		t.Fatal(err)
	}
	outputs, err := model.Predict(Tensors{"demo_in": {1}})
	if err != nil || outputs["demo_out"][0] != 3 || model.Info().Flavour != "static" {
		t.Fatalf("outputs: got %v %v", outputs, err)
	}
}

func TestLoader_MalformedProjectIsALoadError(t *testing.T) {
	damage := map[string]func(directory string){
		"truncated": func(directory string) {
			_ = os.WriteFile(filepath.Join(directory, "project.json"), []byte("{\"na"), 0o600)
		},
		"changed": func(directory string) {
			_ = os.WriteFile(filepath.Join(directory, "golden.json"), []byte(" "), 0o600)
		},
		"absent":  func(directory string) { _ = os.Remove(filepath.Join(directory, "signature.json")) },
		"missing": func(directory string) { _ = os.Remove(filepath.Join(directory, "project.json")) },
	}
	for name, change := range damage {
		directory := project(t, 3, "FP64", 3)
		change(directory)
		if _, err := Load(directory); kindOf(err) != KindLoad {
			t.Errorf("%s: got %v want a Load error", name, err)
		}
	}
}

func TestLoader_MissingRequiredInputIsASignatureError(t *testing.T) {
	model, err := Load(project(t, 3, "FP64", 3))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := model.Predict(Tensors{}); kindOf(err) != KindSignature {
		t.Fatalf("got %v want a Signature error", err)
	}
}

func TestLoader_IntegerOutputThatIsNotAnIntegerIsARuntimeError(t *testing.T) {
	for _, value := range []float64{1.5, math.Pow(2, 60)} {
		model, err := Load(project(t, value, "INT64", 0))
		if err != nil {
			t.Fatal(err)
		}
		if _, err := model.Predict(Tensors{"demo_in": {1}}); kindOf(err) != KindRuntime {
			t.Errorf("value [%v]: got %v want a Runtime error", value, err)
		}
	}
}

func TestLoader_GoldenDifferenceIsAVerifyError(t *testing.T) {
	model, err := Load(project(t, 3, "FP64", 9))
	if err != nil {
		t.Fatal(err)
	}
	if err := model.Verify(); kindOf(err) != KindVerify {
		t.Fatalf("got %v want a Verify error", err)
	}
}
