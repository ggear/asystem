package window

type CountWindow struct {
}

func NewCountWindow() (*CountWindow, error) {
	// TODO: Provide implementation
	return nil, nil
}

func (w *CountWindow) Tick() {
}

func (w *CountWindow) Push(value int) {
}

func (w *CountWindow) PushAndTick(value int) {
}

func (w *CountWindow) PulseLast() int   { return 0 }
func (w *CountWindow) PulseMean() int   { return 0 }
func (w *CountWindow) PulseMedian() int { return 0 }
func (w *CountWindow) PulseMax() int    { return 0 }
func (w *CountWindow) PulseMin() int    { return 0 }
func (w *CountWindow) TrendMean() int   { return 0 }
func (w *CountWindow) TrendMax() int    { return 0 }
func (w *CountWindow) TrendMin() int    { return 0 }
