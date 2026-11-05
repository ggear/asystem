package main

import (
	"encoding/json"
	"fmt"
	"os"

	ort "github.com/yalue/onnxruntime_go"
)

func loadOnnx(path string, signatureJSON string) (func(map[string][]float64) (map[string][]float64, error), error) {
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
	ort.SetSharedLibraryPath(os.Getenv("ONNXRUNTIME_LIB"))
	if err := ort.InitializeEnvironment(); err != nil {
		return nil, fmt.Errorf("onnxruntime unavailable [%w]", err)
	}
	outputNames := make([]string, len(sig.Outputs))
	for index, entry := range sig.Outputs {
		outputNames[index] = entry.Name
	}
	return func(inputs map[string][]float64) (map[string][]float64, error) {
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
		outputs := map[string][]float64{}
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
