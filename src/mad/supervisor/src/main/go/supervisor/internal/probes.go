package internal

import (
	"errors"
	"golang.org/x/exp/constraints"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
)

func compute() error {
	computeUsedProcessorWindow, err := NewDualWindow(1, 5, 1)
	if err != nil {
		return err
	}
	computeUsedProcessorFloats, err := cpu.Percent(time.Second, false)
	if err != nil {
		return err
	}
	if computeUsedProcessorFloats == nil || len(computeUsedProcessorFloats) != 1 {
		return errors.New("failed to get CPU usage")
	}
	computeUsedProcessorInt, err := cast(computeUsedProcessorFloats[0])
	if err != nil {
		return err
	}
	computeUsedProcessorWindow.push(computeUsedProcessorInt)
	return nil
}

func cast[T constraints.Integer | constraints.Float](value T) (int8, error) {
	valueWide := float64(value)
	if valueWide >= 0 && valueWide <= 1 {
		valueWide *= 100
	}
	if valueWide < 0 {
		return -1, errors.New("value must be >= 0")
	}
	if valueWide > 100 {
		return -1, errors.New("value must be <= 100")
	}
	return int8(valueWide + 0.5), nil
}
