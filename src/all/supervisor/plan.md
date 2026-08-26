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

## Decisions (resolved 2026-08-26)

1. **Carrier — `ValueData.Failed bool`**, `failed,omitempty`, with `Pulse` kept non-nil. The removal protocol,
   the host-scope publish guard and the retained topic are all untouched; the display reads one field.
2. **Service scope — blank the cells and paint the service name in `colourAlert`**, reusing the per-row hook
   `drawValue` already has for `serviceRunStateSleeping`.
3. **Warming up — blank, no alert colour.** `errProbeWarmingUp` is not a fault, so it must not set `Failed`.
4. **Stale value — skip the database write when `Failed`, keep the last value in the payload.** No stale point
   per pulse in InfluxDB, and an older watch that ignores the field degrades to today's behaviour rather than
   showing a confident zero.
5. **`Failed` joins `ValueData.Equal`.** Not optional: `Equal` compares only `Pulse` and `Trend`, so without it
   neither entering nor leaving failure marks the record dirty — `cache.Take()` would not publish the change
   until the next heartbeat (up to 5 minutes) and the watch would not repaint at all.
6. **Warming up skips `Store` for host scope only**, with a startup assertion that no service-scope metric can
   return `errProbeWarmingUp`. Skipping `Store` stops a service refreshing, and an unrefreshed service is
   exactly what the reconcile reaps.
7. **Sleeping wins over failed.** A slept service keeps its `colourChat` row and blanks its cells without the
   alert colour, for the same reason an inert metric stays green.
8. **A failed metric counts `unknown` in the census**, not red, so the census agrees with what is on screen.
   The `not green` list still names it.

## Why the carrier is a field and not a nil pulse

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
   as built. Never set it for `derivation.inert` (a legitimate zero on a host with nothing to measure).
3. **Render warming up as no reading, host scope only.** Skip the `Store` while warming up: the seeded nil
   record stays, the existing no-pulse path blanks the box, and nothing is published. Add the assertion
   beside `verifyProbes`/`verifyGates` that no service-scope metric's probe can return `errProbeWarmingUp`,
   since not storing stops a service refreshing and the reconcile reaps an unrefreshed service — a warming-up
   service metric would otherwise remove the row and compact every slot below it.
4. **Skip the database write when `Failed`.** `databaseBatch.add` currently skips only a nil pulse, so a
   failed record would write its stale value every pulse.
5. **Blank on the host grid.** In `drawValue`, treat `record.Value.Failed` like the existing no-pulse case for
   the value area, and paint `lblMid` in `colourAlert` so the box still reads as broken. Add `Failed` to
   `ValueData.Equal` in the same change, or nothing repaints or republishes on the transition.
6. **Signal per row on the service grid.** Service metric boxes have no label of their own — the row is
   labelled by the `MetricServiceName` box — and most are one-character `valBool` cells, so blanking alone is
   invisible. Paint the *service name* in `colourAlert` when any of that service's metrics is failed, reusing
   the per-row colour hook `drawValue` already has for `serviceRunStateSleeping` — and let sleeping win, so a
   slept service keeps `colourChat`.
7. **Count a failed metric `unknown`.** `metricStatusOf` and its test, plus the census columns.
8. **Declare it.** Add the field to `metric.Payloads()`, run `fab generate`, review the broker leaf diff.
9. **Tests.** One golden layout with a blanked host box, one with an alert-coloured service name and one with
   a failed row beside an overflow (`~`) row; a `probe` test that a failed sample stores `Failed` and does not
   push to stats; a `metric_value` round-trip and an `Equal` test for the new field; a `metric_cache` test
   that entering and leaving failure marks the record dirty; an `engine` test that a failed record never
   reaches `removeService`.

## Gaps

The decisions above close the design questions, including the three lifecycle hazards found second: the
dirty-tracking miss, the reap of a warming-up service, and the sleeping-versus-failed collision. What remains
is verification during implementation.

**0. Nothing in this design evicts, deletes or tombstones.** That is the property to hold on to and to test:
a failed metric stores a record like any other, so it refreshes its service, keeps its slot, cannot trigger
`removeService`, and cannot reorder the grid. Every existing add/remove path — empty payload, nil pulse, host
offline, reconcile reap, shutdown tombstone — is reached by exactly the same conditions as before.

**1. Rolling-release skew, both directions.** A release is not atomic across hosts, so during it a new `serve`
publishes `failed` to an old `watch` (which ignores it and shows the last value in red, today's behaviour --
acceptable) and an old `serve` publishes no `failed` to a new `watch` (which can never blank -- also today's
behaviour). Neither is a fault, but the new field must stay `omitempty` so an old watch's unmarshal is
unaffected, and that wants an explicit test rather than an assumption.

**2. `removeService` with an empty service name is unverified.** `Evict(host, "")` / `Delete(host, "")`. No
current path reaches it, and this design keeps it that way, but any future change that lets a host-scope
record arrive with a nil pulse would. Worth an early return regardless.

**3. `isLast` reads the *next* service's record to decide the `~` marker.** `drawValue` loads
`(ID, Host, maxServices)` and tests its pulse. Failed records keep a pulse, so this is expected to be
unaffected -- confirm rather than assume, since a wrong `~` reads as slot corruption.

**4. Skipping `statsFunc` leaves a hole in the window, not a zero.** That is the intent. Confirm `IntStats`
and `FloatStats` tolerate a missed `Push` between `Tick`s without skewing the trend; both are tick-driven, so
this is expected to be fine.

**5. A blank cell in a service row already means two other things** -- the `~` overflow marker and the empty
slot left by an `Evict` without a `Delete`. The row-level alert colour distinguishes a failure from both, but
the goldens should cover a failed row *beside* an overflow row so the two cannot be confused visually.

**6. Warming up strands its last record if it can ever follow a good reading.** The skip means a host metric
that reported and then returned `errProbeWarmingUp` would keep showing its old value indefinitely. Only
`probe_mounts.go` returns it, and only before the first snapshot; the startup assertion covers the service
scope but not this.

**7. Schema churn.** `failed,omitempty` costs nothing on the wire when absent, but it changes every broker
leaf descriptor for every metric on every host and service. Expect a large, purely declarative `fab generate`
diff, and confirm `vernemq/verify.sh` still passes afterwards.

**8. What counts as failed for a whole-service outage.** A missing container is handled by tombstone and
evict, not by a failed sample, so the row-level signal only fires for docker stat read failures -- which take
all of a service's metrics down at once. Confirm that is the only per-service failure mode.

## Proofs

Each gap has one proof, and each proof is written so that it fails under today's behaviour rather than merely
passing under tomorrow's. Only the first needs Docker.

**Gap 0 and 2 — a failed record never removes a service.** Extend the table in
`TestEngine_RunListeningStreamLoop`, which already publishes through a real VerneMQ container and already
holds the negative control beside it (`happy_nil_mqtt_value_deletes_service`). Publish
`{"timestamp":…,"failed":true,"pulse":{"ok":false,"value":42}}`, wait past `reconcileGrace` (the test already
lowers it to a second, so the reap runs inside the case), then assert: the record still loads with `Failed`
true; **a second service registered alongside keeps its `ServiceIndex`**, which is the compaction proof rather
than mere survival; and a subsequent `{}` on the same topic still deletes. The pairing is the proof — the same
test shows the removal path intact and the failed payload passing through `onData`'s `len(payload) == 0` and
`Pulse == nil` branches untouched.

**Gap 3 and 5 — the two blanks cannot be confused.** `TestDisplay_Happy` seeds every service metric per host
through its `record(id, i)` helper and diffs a whole frame against a golden. Add a case with more services
than `maxServices`, which produces the `~`, and mark one *visible* service's metrics failed: the golden then
carries a `~` and a blanked cell on adjacent rows, and any later change that renders them alike breaks the
diff. Because the comparison is the entire frame, it also catches column drift. Then vary it so the
**off-grid** service — the one `isLast` loads at `maxServices` — is the failed one: a failed record keeps its
pulse, so `~` must still appear, and a future "fix" that makes `isLast` skip failed records fails here.

**Gap 4 — a missed `Push` is a hole, not a zero.** Table test in `stats_int_test.go` and `stats_float_test.go`
with no clock: two windows ticked the same number of times, one pushed every tick and one pushed once then
skipped. Assert the skipped window's `TrendMean`, `TrendMin` and `TrendMax` still equal the value pushed. This
fails loudly under today's behaviour, where `statsFunc(0)` on a failed sample drags the mean toward zero, so
it proves Phase 1 did what it claims rather than merely not crashing.

**Gap 1 — rolling-release skew, both directions.** All in `metric_value_test.go`, plus one cache test:
  - marshal a healthy value and assert the bytes are **byte-identical** to a golden string, which is the
    `omitempty` proof that an old watch sees exactly the payload it sees today;
  - unmarshal a *failed* payload into a struct without the field and assert the record survives with its pulse
    intact, so an old watch degrades to red-with-a-stale-value and never to a deletion;
  - unmarshal a payload carrying no `failed` key and assert `Failed == false`;
  - assert two values differing only in `Failed` are **unequal**, and add a `metric_cache` test that `Store`
    marks the record dirty across that transition. That last one is the cheapest test in the set and the only
    thing standing between this design and a five-minute-stale remote watch.

**Gap 7 — schema churn is a review gate, not a test.** Run `fab generate` and require `git diff --name-status`
to show only `M` lines under `src/build/resources/schema/vernemq/model/**` — no additions or deletions, so the
topic *set* is unchanged — and nothing at all under `src/main/resources/image/broker/**`, since the discovery
JSON must not move. Then `verify.sh` against production must still report no drift. Know its limit: `verify.sh`
compares declared against retained *topics* and deliberately does not assert payload shape, so it cannot catch
a wrong descriptor. The diff review is the check that matters.

**Gap 6 and 8 — the two that are assertions, not tests.** The service-scope `errProbeWarmingUp` assertion runs
at startup beside `verifyProbes`/`verifyGates`, so it is proved by existing coverage the moment a service
probe gains the behaviour. For the whole-service outage question, grep the service probe for its error paths
and confirm docker stat failure is the only one that is not already a tombstone.

## Out of scope

- Changing any rule, gate or threshold. `derivation.inert` stays exactly as it is: it is the marker for "green
  because there is nothing to measure here", and it is what keeps a fanless Pi's fan rule from reading red.
- The nine `stub[T]` metrics. They return a real zero and are permanently green by design; blanking them would
  hide the TODO rather than surface it.
