# Watch stream contract

How a `watch` learns which services a host runs, why the current answer is inferred rather than
stated, and what replaces it. Status is marked per section: **built** is in the repo today,
**planned** is not. The goal is a smaller contract, not a bigger one — every section below either
deletes something or is the one thing that replaces it.

Read *Principle* first, then *Design*. Everything after that is consequence.

---

## Symptoms, built

Two observations from the `10.200.1502` release on `max` and `may`, both real, one of them not yet
explained:

**A stale service held a slot for 13 s after its host came back.** `macmini-may` transitioned online
at `13:47:44`; `letsencrypt` — which the release had moved to `max` — was reaped at `13:47:57`. That
is `reconcileDelay` (10 s, being `max(2*pulse, reconcileGrace)`) rounded up to the next
`purgeInterval` (6 s). The window is **10 s best case, 16 s worst**, by construction. The watch had
no way to learn sooner: `may` published nothing about `letsencrypt`, and *absence* is what the
reconcile has to wait out.

**A row stayed blank for one pulse, and only for some services.** `mlflow` was blank while `mlserver`
painted in the same pulse, both being ghosts on `may` (configured, not running). **The mechanism is
unconfirmed** and this plan does not assume one — see *Phase 0*.

Two contributing facts found while diagnosing, both worth fixing on their own merits:

- **The publish batch is map-ordered.** `RecordCache.Take` builds its slice by ranging a map
  (`metric_cache.go:594`) and `process` consumes it in that order (`engine.go:736`), as does the
  `forceRepublish` replay. A service's `name` breadcrumb is therefore published at a random position
  relative to the eight values it announces, re-rolled per service per pulse. That is the shape of
  "one service blank, its neighbour painted", which is why it is a lead — but retained delivery on
  subscribe *should* close the gap whichever way the coin lands, so it is not yet a cause.
- **`serve`'s own crash recovery did not fire.** `may` logged **zero** `rediscovered` lines on
  restart despite `letsencrypt` topics being retained under it. The per-poll tombstone loop can only
  reach services already in `serve`'s cache, and after a restart that cache holds only what the
  `+/name` scan found. When the scan finds nothing, a departed service's retained topics are
  orphaned with no owner left to clear them. They survived here only because the *old* process
  tombstoned on the way down — the graceful path, not the crash path.

---

## Principle

**The watch's model of "which services exist on host H" is accumulated from breadcrumbs and corrected
by a timeout.** Additions are fast (a `name` topic arrives), removals are slow (nothing arrives, wait
out the grace), and nothing distinguishes *not published yet* from *gone*. Every piece of machinery
around it — the connect-versus-transition cutoff, the grace, the retry, the whole-host reap guard —
exists to manage that ambiguity, and none of it can remove it.

**Local mode already does the right thing.** `Display.Run` (`display.go:437`) picks
`RunListeningProbesLoop` for a single local host, which calls `probe.RunPoll(ctx, nil)` — no broker,
nothing subscribed. `servicesProbe.poll` computes `servicesByName` (config ∪ docker) at the top of
every poll and, in the same pass, evicts and deletes every cached service not in it. Membership and
values are decided together, every 3 s. There is no breadcrumb, no cutoff, no grace — and none of
the symptoms above.

So this is not a new mechanism. It is **making the remote path agree with the local one** by shipping
across the broker the set the local path already computes for free:

> The service set is published by its owner and applied whole. Membership is never inferred from
> absence.

---

## Design, planned

### The roster is a metric

`host/services_roster`, `valueKind` str, `persisted: false`, `pulseRule: Always()`, no `trendRule`
and no `trendFunc`, no display box. Its value is the sorted comma-joined service set — exactly
`servicesByName` after the ghost pass, so it costs nothing to compute.

Making it a metric rather than a bespoke topic is the whole trick. It inherits the record envelope,
the retained publish, the topic template, the `metric.Topics()` broker declaration, the schema leaf,
the `--log-subject` vocabulary, `Store`'s skip-notify-on-equal, and the reconnect replay. None of
that is written. `persisted: false` keeps it out of InfluxDB, so no column and no future
`database_archive_measures` entry if the name ever changes.

It is owned by `servicesProbe` — added to `metrics()` and to a `newCacheMetricTask` in the host-scope
tail of `run()`, beside `host/services_status` and `host/services_max_memory`. Any metric with no
registered probe panics `verifyProbes()` at startup in **every** mode, local included.

It joins `host/up_time`, `host/services_max_memory` and `service/max_memory` as the metrics carrying
neither a `trendRule` nor a `trendFunc`; a roster trend is meaningless and the pairing test enforces
the two go together.

**Naming.** The module's rules say a boolean is `*_status`, consumption is `used_*`, a count is
`failed_*`. A roster is none of those, so `services_roster` is a fourth shape. Accepted rather than
forced into `*_status`, which would claim it is a boolean.

### Watch: three rules, no timers

- **A name in the roster the cache does not hold** → `RegisterService` + `subscribeTopics`.
- **A name the cache holds that the roster omits** → `Evict` **and** `Delete` (paired, per the
  existing rule), then one `cache.Refresh()` because `Delete` reindexes and a moved slot would
  otherwise render its old occupant.
- **A roster stamped no later than the last one applied for that host** → ignored. Same rule that
  already governs reviving a muted host: the publisher's own timestamp decides.

The discovery wildcard is a **1:1 swap**, not an addition:
`topicDiscovery = "supervisor/+/data/service/+/name"` becomes
`topicRoster = "supervisor/+/data/services_roster"`, and `onDiscovery` becomes `onRoster` — same
handler shape, same `proveOnline` guard, same register-and-subscribe call, except it takes N names
and also reaps. That collapses estate discovery from ~200 retained topics to 6.

`service/name` stays as a displayed value in the per-service bindings, and as `serve`'s crash
breadcrumb. It stops being the discovery surface.

**The host set is declared, the service set is published.** Hosts come from the watch's own
`hosts` list (CLI/config, max 9) and are seeded at startup from `cache.ListenerIDs()`. Only services
are discovered. A host that never publishes renders blank and ages out through `Purge`'s host-level
eviction; it is never "discovered" and never removed.

### Serve: publish it, and read it back

- Publish the roster **retained at QoS 1**, unlike every other topic. Per-topic publishes are QoS 0
  (`engine.go:743`) and that is right for a value republished every pulse — a lost packet self-heals
  next tick. The roster is not republished every pulse: `Store` skips `notify` on an equal value, so
  an unchanged roster goes quiet until the 300 s heartbeat. A lost roster change would therefore
  strand the watch for up to five minutes. QoS 1 closes that, and the subscribe side is already
  QoS 1 (`engine.go:373`), so only the publish changes.
- At connect, reconcile against the **union of the retained roster and the retained `+/name`
  topics**. The roster is the better source — one topic, one read, complete — but the union costs one
  extra subscribe and is what guarantees orphaned topics get tombstoned when the roster is missing,
  which is exactly the case `may` demonstrated.

---

## The rewritten contract, planned

This is the acceptance test for the whole plan. The doc comment on `RunListeningStreamLoop` is
currently ~45 lines describing four interacting timers and cutoffs. If it does not come out at
roughly this size, something inferential is still in there:

```
// On connect:
//  1. Forget the host status, the subscribed topics and the last roster applied per host, none of
//     which survive a new session.
//  2. Subscribe to every topic the cache already holds, in one packet.
//  3. Subscribe to the roster and to host status, tracking both so a refused subscribe is retried.
//  4. Refresh the display, so a reconnect cannot leave the screen on the nils it slept with.
//
// On a roster:
//  1. Ignore one stamped no later than the last applied for that host.
//  2. Register and subscribe every name the cache does not hold.
//  3. Evict and delete every service the roster omits, then refresh if anything was reaped.
//
// On a data message:
//  1. Ignore a topic the subscribed map does not hold, counting it as dropped.
//  2. Remove the service on an empty or nil pulse payload, being the tombstone a live host
//     publishes when a service departs.
//  3. Revive an offline host when the payload was published after the offline.
//  4. Ignore anything else from an offline host.
//  5. Stamp and store everything else.
//
// On host status:
//   - offline: evict every service to nil and store nil for the host metrics, which keeps the slots
//     for repopulation.
//   - online after an offline: resubscribe the host, forcing the broker to redeliver its retained
//     set including its roster.
//   - online, unchanged: nothing, this is the heartbeat re-asserting a status already held.
//
// On the purge tick:
//  1. Evict the records of a silent host to nil, then delete a service whose records stayed nil.
//  2. Resync the subscribed topics against the cache.
//  3. Restore either wildcard subscription the connect failed to establish.
//  4. Revive a client paho has abandoned.
//  5. Resubscribe everything after five silent ticks.
//  6. Report the traffic and the census.
```

Note what leaves the *connect* case: an online transition first-since-connect needs no action at all,
because the connect already subscribed the roster wildcard and the retained roster is in flight.

---

## Edge cases, worked

| # | Case | Handled by |
|---|---|---|
| 1 | Roster arrives while its host is muted offline | Goes through `proveOnline` exactly as data does, so a wrongly-muted host recovers its set on the first roster stamped after the offline. Without this a mute is permanent. |
| 2 | Roster names services the watch has never subscribed to | Register → subscribe → retained values delivered at subscribe. Values published before the subscribe are retained; after it, live. No gap either way. |
| 3 | Roster reaps a service whose records are still in flight | The reap unsubscribes, so late records hit the subscribed-map check in `onData` and are counted dropped. |
| 4 | Roster and tombstone disagree | Cannot happen within a pulse: the roster is sampled from `servicesByName`, which already excludes the departing service, and the tombstone for that service is published in the same pulse. Ordering makes it moot, but the roster is authoritative if they ever differ. |
| 5 | Two rosters delivered out of order | Timestamp guard (rule 1). |
| 6 | Roster packet lost | QoS 1. This is the one topic whose loss is not self-healing within a pulse. |
| 7 | vernemq store flushed by a release | No retained anything. The watch reaps nothing, because a reap needs a roster to act on — absence is never evidence. Each `serve` republishes on reconnect via `forceRepublish` and the estate converges. This is the case the deleted whole-host reap guard existed for, and it resolves by construction. |
| 8 | `serve` SIGKILLed and restarted | Reads its own retained roster ∪ `+/name` at connect, tombstones the difference. Strictly stronger than today, which found nothing. |
| 9 | `serve` dies and stays dead | LWT → offline → watch evicts to nil and holds the slots; `Purge` deletes them after the window. Unchanged. |
| 10 | Watch suspends and wakes | `brokerRevive` probes or reconnects. A reconnect re-runs the connect path and the retained roster is applied at once — no grace, no cutoff, which is a strict improvement on today. |
| 11 | Declared host that never publishes | Renders from its seeded nils; unknown host counts as online so it still renders. Never discovered, never reaped. |
| 12 | Same service name on two hosts | Rosters are per host and slots are per host. No interaction. |
| 13 | Roster carrying a malformed or reserved name | Validate on receipt: non-empty, no `/`, not prefixed `ServiceNameSchema` (which `reindex` and the cache both treat specially), and a sanity cap on count. A roster is remote input and must not be able to inject a pseudo-service. |
| 14 | Roster larger than the display's rows | Unchanged — the grid shows N rows and the `~` overflow marker, which already wins over every other cell state. |
| 15 | Local mode | The roster metric is **produced** by `servicesProbe` and **ignored**; `RunListeningProbesLoop` must grow no consumer, or the probe would be reading back its own answer. `RunAllProbesOnce` seeds it with every other ID. |
| 16 | A service in the roster with no values yet | A distinct display state, never a fault and never reaped. See *Phase 3*. |

---

## What gets deleted, planned

Landed as **one change** with the roster, not staged. There is no interest in the mixed-version
estate here, and the intermediate state — reconcile removed, roster not yet in — has no per-service
reaper at all, so it is a state worth never building.

- `scheduleReconcile`, the `reconciles` map, `reconcileMu`, the `hostReconcile` struct
  (`engine.go:847`), the `reconcileGrace` const (`:902`)
- `reconcileDelay` and the `connected` cutoff variable, which exists only to feed `pending.started`,
  and with it the whole `fromConnect` connect-versus-transition distinction
- the deferred-reap guard, `pending.retried`, and its retry resubscribe (`:472`)
- the reconcile block in the purge tick (`:452-490`) and its `reclaims` / `deferred` lines
- `RecordCache.ServicesBefore` (`metric_cache.go:510`), whose only caller this is
- the `reconcileGrace` override in `engine_test.go:406` and the tests built on it

**Kept, and none of it is reconcile machinery:**

- `proveOnline` — unchanged, and the roster must route through it (edge case 1)
- `resubscribeHost` — loses the retry caller, keeps the revive-from-mute (`:153`) and restart (`:327`)
  callers. The revive one matters: the watch discarded messages while it had the host muted and
  `serve` never reconnected, so nothing republishes unprompted.
- `RecordCache.Purge` — orthogonal. It evicts on **host** staleness via `hostLastSeen`
  (`metric_cache.go:423`) and deletes what stayed nil. It has never been a per-service reaper.
- the silence detector, `resyncTopics`, `subscribeWildcards`, the offline eviction path

That leaves exactly three per-service removal paths — **two positive statements** (the roster's set
difference, the tombstone nil-pulse) **and one host-level ageing**. Nothing removes a service by
inferring from absence, which is what every deleted item above was compensating for.

**Surviving notes** from the current doc: the roster proves a host alive exactly as data does;
reaping is keyed by service name and never by slot; a subscribe is refused either by its token or by
a SUBACK return code above the maximum QoS; the display refreshes on connect and after a reap, never
per host and never per heartbeat; an unknown host counts as online.

---

## Phases

### Phase 0 — verify the blank, planned

**Do not build on an unverified premise.** The 13 s stale row is fully explained; the 5 s blank is
not. Reproduce by restarting `serve` on a host with at least two ghost services while running a
remote `watch` with `--log-subject=service/mlflow`, and compare against that host's own
`retained [n] bytes at qos [0]` publish lines for the same service. The question to answer is whether
its value topics were published in the discovery pulse at all. If they were, retained delivery should
have covered it and there is a mechanism still unaccounted for; if they were not, the blank is a
publish-side gap and the roster changes nothing about it.

### Phase 1 — hygiene, independent of everything else, planned

1. **Sort the publish batch.** One `slices.SortFunc` by GUID in `Take` or at the `process` call site.
   Makes a pulse reproducible, which you want *before* reasoning about arrival ordering, and gives
   roster-before-services ordering for free since host metrics carry an empty `ServiceName` and sort
   first. Correctness does not depend on that ordering (edge case 2) — it saves a round trip.
2. **Ghost derivations → `derivedInertf`.** A configured service with no container has nothing to
   sample and already says so; today seven of its metrics return `derivation{}` and log `unstated` at
   ERROR every pulse — 21 a pulse on `may`, 1638 in one uptime. `derivedInertf` also short-circuits
   rule evaluation, so a ghost stops being judged by a rule it cannot satisfy.

### Phase 2 — the roster, planned

The metric, `onRoster` replacing `onDiscovery`, the serve-side QoS-1 publish and connect readback,
and the deletions above. One change. Acceptance test is the doc comment.

### Phase 3 — the third row state, planned

With an authoritative set the display can finally tell **declared but not yet reporting** from
**measured and failed**. Today both render as a blank cell, and on the service grid a failure also
paints the service name in `colourAlert` — so a brand-new service looks broken. Render the awaiting
state neutral, keep `Failed` alert, and keep the existing precedence: sleeping wins over failed, and
the `~` overflow marker wins over both.

This is the reason to do the rest. An empty slot stops being reachable at all, because slots are
allocated from an authoritative list rather than from whatever breadcrumbs happened to arrive.

### Not doing

- **A deadline timer for the reconcile.** It was worth 3 s of the 13 while the reconcile existed;
  the reconcile does not survive Phase 2, so this is moot. Recorded so it is not rediscovered.
- **Filling an empty row from the install tree.** A remote watch has no install tree, and it would be
  a second source of truth for the set this plan exists to make singular.
- **Shortening `reconcileGrace`.** Deleted rather than tuned. It was sized for the redelivery race
  and shortening it reintroduces false reaps.
- **A roster consumer in `RunListeningProbesLoop`.** Edge case 15.

---

## Estate note, built

The `10.200.1502` release moved several modules between `max` and `may`, and the containers have not
followed. `max` is configured for cloudflare, grafana, letsencrypt, openra, supervisor while running
letsencrypt, mlflow, mlserver, supervisor; `may` is configured for influxdb3, mlflow, mlserver,
sonarr, supervisor, tempstat while running cloudflare, grafana, sonarr, supervisor, tempstat. So each
host publishes a full record set for ~3 ghosts that live on the other, and `influxdb3` is installed
on `may` but not running, which is why `mad` drops every database write.

None of that is caused by anything in this plan, and none of it is fixed by it. It is the reason the
symptoms were visible, and it should be resolved before Phase 0 is measured, or the reproduction will
be confounded.
