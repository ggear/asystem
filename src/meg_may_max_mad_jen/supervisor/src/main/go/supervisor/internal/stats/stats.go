package stats

type Stats[T any] interface {
	Tick()
	Push(T)
	PushAndTick(T)
	PulseLast() T
	PulseMedian() T
}
