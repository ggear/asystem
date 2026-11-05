package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

func loadServed(url string, signatureJSON string) (func(map[string][]float64) (map[string][]float64, error), error) {
	type tensor struct {
		Name     string    `json:"name"`
		Shape    []int     `json:"shape,omitempty"`
		Datatype string    `json:"datatype,omitempty"`
		Data     []float64 `json:"data"`
	}
	var sig struct {
		Inputs []struct {
			Name     string `json:"name"`
			Datatype string `json:"datatype"`
		} `json:"inputs"`
	}
	if err := json.Unmarshal([]byte(signatureJSON), &sig); err != nil {
		return nil, fmt.Errorf("signature invalid [%w]", err)
	}
	return func(inputs map[string][]float64) (map[string][]float64, error) {
		var request struct {
			Inputs []tensor `json:"inputs"`
		}
		for _, entry := range sig.Inputs {
			if data, supplied := inputs[entry.Name]; supplied {
				request.Inputs = append(request.Inputs, tensor{Name: entry.Name, Shape: []int{len(data)}, Datatype: entry.Datatype, Data: data})
			}
		}
		body, err := json.Marshal(request)
		if err != nil {
			return nil, fmt.Errorf("request invalid [%w]", err)
		}
		client := http.Client{Timeout: 30 * time.Second}
		response, err := client.Post(url, "application/json", bytes.NewReader(body))
		if err != nil {
			return nil, fmt.Errorf("server gave no answer [%w]", err)
		}
		defer response.Body.Close()
		if response.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("server gave status [%d]", response.StatusCode)
		}
		var answer struct {
			Outputs []tensor `json:"outputs"`
		}
		if err := json.NewDecoder(response.Body).Decode(&answer); err != nil {
			return nil, fmt.Errorf("answer invalid [%w]", err)
		}
		outputs := map[string][]float64{}
		for _, output := range answer.Outputs {
			outputs[output.Name] = output.Data
		}
		return outputs, nil
	}, nil
}
