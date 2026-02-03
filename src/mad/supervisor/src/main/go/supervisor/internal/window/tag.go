package window

type TagWindow struct {
}

func NewTagWindow() (*TagWindow, error) {
	// TODO: Provide implementation
	return nil, nil
}

func (w *TagWindow) Tick() {
}

func (w *TagWindow) Push(value string) {
}

func (w *TagWindow) PushAndTick(value string) {
}

func (w *TagWindow) PulseLast() string     { return "" }
func (w *TagWindow) PulseMean() string     { return "" }
func (w *TagWindow) PulseMedian() string   { return "" }
func (w *TagWindow) PulseMax() string      { return "" }
func (w *TagWindow) PulseMin() string      { return "" }
func (w *TagWindow) PulseHasChanged() bool { return false }
func (w *TagWindow) TrendMean() string     { return "" }
func (w *TagWindow) TrendMax() string      { return "" }
func (w *TagWindow) TrendMin() string      { return "" }
func (w *TagWindow) TrendHasChanged() bool { return false }
