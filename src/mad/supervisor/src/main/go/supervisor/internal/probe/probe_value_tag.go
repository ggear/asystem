package probe

type tagValue struct {
}

func newTagValue() (*tagValue, error) {
	// TODO: Provide implementation
	return nil, nil
}

func (v *tagValue) Tick() {
}
func (v *tagValue) Push(value string) {
}
func (v *tagValue) PushAndTick(value string) {
}

func (v *tagValue) PulseLast() string     { return "" }
func (v *tagValue) PulseMean() string     { return "" }
func (v *tagValue) PulseMedian() string   { return "" }
func (v *tagValue) PulseMax() string      { return "" }
func (v *tagValue) PulseMin() string      { return "" }
func (v *tagValue) PulseHasChanged() bool { return false }
func (v *tagValue) TrendMean() string     { return "" }
func (v *tagValue) TrendMax() string      { return "" }
func (v *tagValue) TrendMin() string      { return "" }
func (v *tagValue) TrendHasChanged() bool { return false }
