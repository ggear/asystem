package metric

import "encoding/json"

type ValueData struct {
	Timestamp int64           `json:"timestamp"`
	Pulse     ValueDataDetail `json:"pulse,omitempty"`
	Trend     ValueDataDetail `json:"trend,omitempty"`
}

func (v ValueData) MarshalJSON() ([]byte, error) {
	type Alias struct {
		Timestamp int64            `json:"timestamp"`
		Pulse     *ValueDataDetail `json:"pulse,omitempty"`
		Trend     *ValueDataDetail `json:"trend,omitempty"`
	}
	aux := Alias{Timestamp: v.Timestamp}
	if !v.Pulse.IsZero() {
		aux.Pulse = &v.Pulse
	}
	if !v.Trend.IsZero() {
		aux.Trend = &v.Trend
	}
	return json.Marshal(aux)
}

// noinspection GoMixedReceiverTypes
func (v *ValueData) UnmarshalJSON(data []byte) error {
	type Alias ValueData
	var aux Alias
	if len(data) == 0 || string(data) == `""` {
		return nil
	}
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}
	*v = ValueData(aux)
	return nil
}
