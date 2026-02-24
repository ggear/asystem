package probe

type countValue struct {
}

func newCountValue() (*countValue, error) {
	// TODO: Provide implementation
	return nil, nil
}

func (v *countValue) Tick() {
}
func (v *countValue) Push(value int) {
}
func (v *countValue) PushAndTick(value int) {
}

func (v *countValue) PulseLast() int   { return 0 }
func (v *countValue) PulseMean() int   { return 0 }
func (v *countValue) PulseMedian() int { return 0 }
func (v *countValue) PulseMax() int    { return 0 }
func (v *countValue) PulseMin() int    { return 0 }
func (v *countValue) TrendMean() int   { return 0 }
func (v *countValue) TrendMax() int    { return 0 }
func (v *countValue) TrendMin() int    { return 0 }
