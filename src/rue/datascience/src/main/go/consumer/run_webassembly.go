package main

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"time"

	"github.com/tetratelabs/wazero"
)

func loadWasm(path string, signatureJSON string) (func(map[string][]float64) (map[string][]float64, error), error) {
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
	for name, function := range map[string]func(float64) float64{"atan": math.Atan, "cos": math.Cos, "exp": math.Exp, "log": math.Log, "sin": math.Sin, "tanh": math.Tanh} {
		maths.NewFunctionBuilder().WithFunc(function).Export(name)
	}
	if _, err := maths.Instantiate(ctx); err != nil {
		return nil, fmt.Errorf("maths functions did not instantiate [%w]", err)
	}
	module, err := engine.CompileModule(ctx, bytes)
	if err != nil {
		return nil, fmt.Errorf("module did not compile [%w]", err)
	}
	return func(inputs map[string][]float64) (map[string][]float64, error) {
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
		result := map[string][]float64{}
		position := 0
		for _, entry := range sig.Outputs {
			count := 1
			if isState(entry.Shape) {
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
	}, nil
}
