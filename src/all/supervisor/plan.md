# Plan — blanking a metric whose collection failed

## Goal

When a metric's sample fails, the box should stop showing a number. Hide the bar, the value and the unit
suffix; keep the label, and keep the fault visible as colour rather than as a fake reading. Today a failed
sample paints red over whatever the stats window last held, which is indistinguishable from a real bad
reading, and on a metric that has never worked it is indistinguishable from a genuine zero.

## What already exists (verified, no work needed)

- **The rendering.** `box.drawValue` (`display_layout.go:603`) returns early when the record is missing, has
  no pulse, or the pulse `IsZero()`, painting `valLen + valSfxLen` spaces and leaving the label drawn. The
  space is reserved by `advance(...)` in `box.draw`, so blanking never reflows the grid or trips `Compile`'s
  equal-row-width assertion.
- **A third colour state.** `highlight` treats a nil pulse as neutral, so no new colour is required for the
  "no reading" case; only the *failed* case needs a signal of its own.
- **The fault lifecycle.** `trackMetricFault` already logs ERROR once, DEBUG while it persists and INFO on
  clear, and the census already carries an `unknown` column.
- **The database.** `databaseBatch.add` (`engine_database.go:50`) already skips a record with no pulse, so no
  zero is written for an unmeasured metric.
- **One place decides.** `runMetricCacheTask` (`probe.go`) already computes `errored`, so the whole change has
  a single upstream origin.

## The decision that shapes everything: how "failed" is carried

**Do not reuse a nil pulse.** A nil pulse is already the service-removal protocol on both sides (see Gap 1 and
Gap 2). The proposal is one explicit field:

```go
type ValueData struct {
	Timestamp int64            `json:"timestamp"`
	Failed    bool             `json:"failed,omitempty"`
	Pulse     *ValueDataDetail `json:"pulse,omitempty"`
	Trend     *ValueDataDetail `json:"trend,omitempty"`
}
```

`Pulse` stays present and non-nil on a failed sample (`OK:false`, carrying the last computed value), so every
existing protocol rule holds unchanged; `Failed` is the only thing the display reads to decide to blank. A
`ValueDataDetail{Kind: ValueNone}` cannot serve as the marker — its `MarshalJSON` emits `null` and unmarshal
maps that back to a nil pointer, which is exactly the removal signal.

## Phases

1. **Stop poisoning the stats window.** In `runMetricCacheTask`, skip `task.statsFunc(sample)` when `errored`.
   Today the failed sample's zero is pushed before the error is considered, so a broken probe drags the pulse
   and trend windows down for the whole trend window even after it recovers. This is worth doing on its own
   merits and is independent of the display.
2. **Carry the state.** Add `ValueData.Failed`, set it in `runMetricCacheTask` when `errored`, leave `Pulse`
   as built. Do not set it for `errProbeWarmingUp` (no reading yet, not a fault) and never for
   `derivation.inert` (a legitimate zero on a host with nothing to measure).
3. **Blank on the host grid.** In `drawValue`, treat `record.Value.Failed` like the existing no-pulse case for
   the value area, and paint `lblMid` in `colourAlert` so the box still reads as broken.
4. **Signal per row on the service grid.** Service metric boxes have no label of their own — the row is
   labelled by the `MetricServiceName` box — and most are one-character `valBool` cells, so blanking alone is
   invisible. Paint the *service name* in `colourAlert` when any of that service's metrics is failed, reusing
   the per-row colour hook `drawValue` already has for `serviceRunStateSleeping`.
5. **Declare it.** Add the field to `metric.Payloads()`, run `fab generate`, review the broker leaf diff.
6. **Tests.** One golden layout with a blanked host box and one with an alert-coloured service name; a
   `probe` test that a failed sample stores `Failed` and does not push to stats; a `metric_value` round-trip
   test for the new field.

## Gaps

**1. A nil pulse already means "remove this service" — blocking.** On the watch side `onData`
(`engine.go:184`) does `if value.Pulse == nil { removeService(guid) }`, and an empty payload does the same.
On the serve side `process` (`engine.go:732`) publishes a service record with a nil pulse as JSON *and then*
as an empty payload, and appends the service to `toDelete`. So the obvious implementation — store
`NewNilValue()` on error — would tombstone the entire service on every watch the first time one docker stat
read failed. This is why the design above keeps `Pulse` non-nil.

**2. A failed host metric cannot currently be expressed over MQTT — blocking for remote watch.** In the same
`process`, the nil-pulse branch is guarded by `guid.ServiceName != metric.ServiceNameUnset`, so a host-scope
record with no pulse is *not published at all*. Its retained topic keeps the last good value, and a remote
watch keeps drawing that number indefinitely while a local watch on the same host blanks it. The `Failed`
field fixes this by keeping the record publishable, but the divergence between `-m local` and `-m remote`
must be tested explicitly — it is the difference between a dashboard that lies and one that does not.

**3. `removeService` with an empty service name is unverified.** `Evict(host, "")` / `Delete(host, "")` — no
current path reaches it, but any future change that lets a host-scope record arrive with a nil pulse would.
Worth an assertion or an early return regardless of this work.

**4. The display cannot tell "failed" from "never reported" without the new field.** Both are a nil pulse
today. If Phase 2 is skipped and `NewNilValue` used instead, the box goes blank *and silent* — no colour, no
distinction from a host that has not reported yet — and the only evidence of the fault is the log. Decide
deliberately; the recommendation is the explicit field.

**5. A blank cell in a service row already means two other things.** The `~` overflow marker on `isLast`, and
the empty slot left by an `Evict` without a `Delete`. Adding a third meaning makes the slot-compaction bugs
harder to see, which is the second reason Phase 4 signals on the row rather than the cell.

**6. `isLast` reads the *next* service's record to decide the `~` marker.** `drawValue` loads
`(ID, Host, maxServices)` and checks its pulse. If failed records change what is stored, re-check that logic —
it currently keys off pulse presence alone.

**7. Skipping `statsFunc` leaves a hole in the window, not a zero.** That is the intent, but confirm
`IntStats`/`FloatStats` tolerate a missed `Push` between `Tick`s without skewing the trend (they are
tick-driven, so this is expected to be fine — verify rather than assume).

**8. Retained-topic drift.** If a failed host metric is ever published as an *empty* payload instead of a
`Failed` record, its retained topic disappears and `vernemq/verify.sh` reports it `missing` on every run
until the metric recovers. The `Failed` design avoids this; any alternative must account for it.

**9. Payload size and schema churn.** `failed,omitempty` costs nothing when absent, but it does change every
broker leaf descriptor for every metric, on every host and service. Expect a large `fab generate` diff that is
pure declaration, and confirm `verify.sh` still passes afterwards.

**10. What counts as failed for a whole-service outage.** A missing container is handled by tombstone and
evict, not by a failed sample, so Phase 4 only fires for docker stat read failures — which take *all* of a
service's metrics down at once. Confirm that is the only per-service failure mode before building a per-metric
signal for it.

## Out of scope

- Changing any rule, gate or threshold. `derivation.inert` stays exactly as it is: it is the marker for "green
  because there is nothing to measure here", and it is what keeps a fanless Pi's fan rule from reading red.
- The nine `stub[T]` metrics. They return a real zero and are permanently green by design; blanking them would
  hide the TODO rather than surface it.
