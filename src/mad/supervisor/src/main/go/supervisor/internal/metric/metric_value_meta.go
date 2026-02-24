package metric

type ValueMeta struct {
	Version string           `json:"version"`
	Pulse   *ValueMetaDetail `json:"pulse,omitempty"`
	Trend   *ValueMetaDetail `json:"trend,omitempty"`
}

type ValueMetaDetail struct {
	Window  string `json:"window"`
	Unit    string `json:"unit,omitempty"`
	Type    string `json:"type"`
	Measure string `json:"measure"`
}
