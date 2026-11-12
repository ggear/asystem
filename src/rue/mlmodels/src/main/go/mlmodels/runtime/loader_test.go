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

func identified(t *testing.T, directory string) string {
	t.Helper()
	signatureBytes, err := os.ReadFile(filepath.Join(directory, "signature.json"))
	if err != nil {
		t.Fatal(err)
	}
	var signature map[string]any
	if err := json.Unmarshal(signatureBytes, &signature); err != nil {
		t.Fatal(err)
	}
	signature["signature_version"] = 1001
	signatureBytes, _ = json.Marshal(signature)
	if err := os.WriteFile(filepath.Join(directory, "signature.json"), signatureBytes, 0o600); err != nil {
		t.Fatal(err)
	}
	manifestBytes, err := os.ReadFile(filepath.Join(directory, "project.json"))
	if err != nil {
		t.Fatal(err)
	}
	var manifest map[string]any
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		t.Fatal(err)
	}
	manifest["model_id"] = 1005
	sum := sha256.Sum256(signatureBytes)
	manifest["files"].(map[string]any)["signature.json"] = hex.EncodeToString(sum[:])
	manifestBytes, _ = json.Marshal(manifest)
	if err := os.WriteFile(filepath.Join(directory, "project.json"), manifestBytes, 0o600); err != nil {
		t.Fatal(err)
	}
	contentSum := sha256.Sum256(manifestBytes)
	return hex.EncodeToString(contentSum[:])
}

func release(t *testing.T, directory string, contentSha256 string) {
	t.Helper()
	content, _ := json.Marshal(map[string]any{"schema": 1, "version": "10.200.2027", "released_at": "2026-11-12T09:05:35Z", "content_sha256": contentSha256})
	if err := os.WriteFile(filepath.Join(directory, "release.json"), content, 0o600); err != nil {
		t.Fatal(err)
	}
}

func TestLoader_ReleasedProjectReportsItsVersionsAndHashes(t *testing.T) {
	directory := project(t, 3.5, "FP64", 3.5)
	contentSha256 := identified(t, directory)
	release(t, directory, contentSha256)
	model, err := Load(directory)
	if err != nil {
		t.Fatal(err)
	}
	info := model.Info()
	if info.ContentSha256 != contentSha256 || info.ModelID == nil || *info.ModelID != 1005 || info.SignatureVersion == nil || *info.SignatureVersion != 1001 {
		t.Fatalf("info: got %+v", info)
	}
	if info.ReleaseVersion == nil || *info.ReleaseVersion != "10.200.2027" || info.ReleasedAt == nil || *info.ReleasedAt != "2026-11-12T09:05:35Z" {
		t.Fatalf("release: got %+v", info)
	}
	if len(info.Files) != 2 || info.Files["signature.json"] == "" || info.Files["golden.json"] == "" {
		t.Fatalf("files: got %v", info.Files)
	}
}

func TestLoader_UnreleasedProjectReportsNoRelease(t *testing.T) {
	model, err := Load(project(t, 3.5, "FP64", 3.5))
	if err != nil {
		t.Fatal(err)
	}
	info := model.Info()
	if info.ModelID != nil || info.SignatureVersion != nil || info.ReleaseVersion != nil || info.ReleasedAt != nil {
		t.Fatalf("info: got %+v", info)
	}
}

func TestLoader_ReleaseFileForAnotherProjectIsALoadError(t *testing.T) {
	directory := project(t, 3.5, "FP64", 3.5)
	release(t, directory, "0000000000000000000000000000000000000000000000000000000000000000")
	_, err := Load(directory)
	modelError, ok := errors.AsType[*ModelError](err)
	if !ok || modelError.Kind != KindLoad || modelError.Gate != "release" {
		t.Fatalf("error: got %v", err)
	}
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
