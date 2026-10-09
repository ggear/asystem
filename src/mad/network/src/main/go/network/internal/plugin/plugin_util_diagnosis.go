package plugin

import (
	"network/internal/schema"
)

var (
	diagnosis       = schema.Declare("diagnosis/plugin", "health and diagnosis score of one network plugin", aggregateCadence)
	diagnosisPlugin = diagnosis.Subject("plugin", "name of the diagnosed plugin")
	diagnosisOK     = diagnosis.Bool("ok", "plugin reported a fit or sick diagnosis rather than dead").Levels(schema.Truthy())
	diagnosisScore  = diagnosis.Int("score", "", "diagnosis score from 0 to 100")
)

func Diagnose(status Status, score int, reason string) Aggregate {
	return Aggregate{Status: status, OK: status != StatusDead, Score: score, Reason: reason}
}

func DiagnosisPoint(name string, ok bool, score int) schema.Point {
	return diagnosis.Point(diagnosisPlugin.Of(name), diagnosisOK.Of(ok), diagnosisScore.Of(int64(score)))
}

func clamp(v int) int {
	return min(max(v, 0), 100)
}
