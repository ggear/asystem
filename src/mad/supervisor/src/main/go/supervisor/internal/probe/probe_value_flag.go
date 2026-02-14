package probe

type flagValue struct {
}

func NewFlagWindow() (*flagValue, error) {
	// TODO: Provide implementation
	return nil, nil
}

func (v *flagValue) Tick() {
}
func (v *flagValue) Push(value bool) {
}
func (v *flagValue) PushAndTick(value bool) {
}

func (v *flagValue) PulseLast() bool       { return false }
func (v *flagValue) PulseMean() bool       { return false }
func (v *flagValue) PulseMedian() bool     { return false }
func (v *flagValue) PulseHasTrue() bool    { return false }
func (v *flagValue) PulseHasFalse() bool   { return false }
func (v *flagValue) PulseHasChanged() bool { return false }
func (v *flagValue) TrendMean() bool       { return false }
func (v *flagValue) TrendHasTrue() bool    { return false }
func (v *flagValue) TrendHasFalse() bool   { return false }
func (v *flagValue) TrendHasChanged() bool { return false }
