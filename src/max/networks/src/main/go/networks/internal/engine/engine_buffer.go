package engine

import "networks/internal/plugin"

type sampleBuffer struct {
	ring []plugin.Sample
	head int
	full bool
}

func newSampleBuffer(capacity int) *sampleBuffer {
	if capacity < 1 {
		capacity = 1
	}
	return &sampleBuffer{ring: make([]plugin.Sample, capacity)}
}

func (b *sampleBuffer) Add(m plugin.Sample) {
	b.ring[b.head] = m
	b.head = (b.head + 1) % len(b.ring)
	if b.head == 0 {
		b.full = true
	}
}

func (b *sampleBuffer) Len() int {
	if b.full {
		return len(b.ring)
	}
	return b.head
}

func (b *sampleBuffer) Samples() []plugin.Sample {
	n := b.Len()
	if n == 0 {
		return nil
	}
	out := make([]plugin.Sample, n)
	if !b.full {
		copy(out, b.ring[:b.head])
		return out
	}
	for i := 0; i < n; i++ {
		out[i] = b.ring[(b.head+i)%len(b.ring)]
	}
	return out
}

func (b *sampleBuffer) Reset() {
	b.head = 0
	b.full = false
	for i := range b.ring {
		b.ring[i] = plugin.Sample{}
	}
}
