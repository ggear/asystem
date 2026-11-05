package main

import (
	"encoding/json"
	"fmt"
)

func loadStatic(constantsJSON string, signatureJSON string) (func(map[string][]float64) (map[string][]float64, error), error) {
	var constants map[string]float64
	if err := json.Unmarshal([]byte(constantsJSON), &constants); err != nil {
		return nil, fmt.Errorf("constants invalid [%w]", err)
	}
	return func(map[string][]float64) (map[string][]float64, error) {
		outputs := map[string][]float64{}
		for name, value := range constants {
			outputs[name] = []float64{value}
		}
		return outputs, nil
	}, nil
}
