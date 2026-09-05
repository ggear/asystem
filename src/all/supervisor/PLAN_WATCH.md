# Watch stream contract

How a `watch` learns which services a host runs, why the current answer is inferred rather than
stated, and what should replace it. Status is marked per section: **built** is in the repo today,
**planned** is not.

Read *Symptoms* and *Principle* first, then *Options* — which compares four changes of very different
size, because the smallest one captures a third of the benefit and the largest is not obviously worth
its risk. Everything after that is the detail of the two recommended.

---

## Symptoms, built

Two observations from the `10.200.1502` release on `max` and `may`, both real, one of them not yet
explained.

**A stale service held a slot for 13 s after its host came back.** `macmini-may` transitioned online
at `13:47:44`; `letsencrypt` — which the release had moved to `max` — was reaped at `13:47:57`. That
is `reconcileDelay` (10 s, being `max(2*pulse, reconcileGrace)`) rounded up to the next
`purgeInterval` (6 s), so the window is **10 s best case, 16 s worst**, by construction. The watch had
no way to learn sooner: `may` published nothing about `letsencrypt`, and *absence* is what the
reconcile has to wait out.

**A row stayed blank for one pulse, and only for some services.** `mlflow` was blank while `mlserver`
painted in the same pulse, both being ghosts on `may` (configured, not running). **The mechanism is
unconfirmed** and nothing here assumes one — see *Phase 0*.

Two contributing facts found while diagnosing, both worth fixing on their own merits:

- **`serve`'s own crash recovery did not fire.** `may` logged **zero** `rediscovered` lines on
  restart despite `letsencrypt` topics being retained under it. The per-poll tombstone loop can only
  reach services already in `serve`'s cache, and after a restart that cache holds only what the
  `+/name` scan found. When the scan finds nothing, a departed service's retained topics are orphaned
  with no owner left to clear them. They survived here only because the *old* process tombstoned on
  the way down — the graceful path, not the crash path. **This is a correctness hole, not a latency
  problem, and no constant fixes it.**
- **The publish batch is map-ordered.** `RecordCache.Take` builds its slice by ranging a map
  (`metric_cache.go:594`) and `process` consumes it in that order (`engine.go:736`), as does the
  `forceRepublish` replay. A service's `name` breadcrumb is published at a random position relative
  to the eight values it announces, re-rolled per service per pulse. That is the shape of "one
  service blank, its neighbour painted" — but retained delivery on subscribe *should* close the gap
  whichever way the coin lands, so it is a lead, not a cause.

---

## Principle

**The watch's model of "which services exist on host H" is accumulated from breadcrumbs and corrected
by a timeout.** Additions are fast, removals are slow, and nothing distinguishes *not published yet*
from *gone*. Every mechanism around it — the connect-versus-transition cutoff, the grace, the retry,
the whole-host reap guard — exists to manage that ambiguity and none of it can remove it.

**Local mode does not have the problem.** `Display.Run` (`display.go:437`) picks
`RunListeningProbesLoop` for a single local host, which calls `probe.RunPoll(ctx, nil)` — no broker,
nothing subscribed. `servicesProbe.poll` computes `servicesByName` (config ∪ docker) at the top of
every poll and, in the same pass, evicts and deletes every cached service not in it. Membership and
values are decided together, every 3 s.

The property to copy is not "publish a list". It is narrower and more useful:

> Membership is answered by a **query of current state**, never by an accumulation corrected with a
> timeout.

Locally that query is "what does docker report". Remotely there are two candidate queries — *what
does the broker retain right now* (the barrier, below) and *what does the host say it has* (the
roster, below). Both satisfy the principle. They differ in what they cost and what they can be wrong
about.

---

## Options

| | Change | Touches | Deletes | Fixes |
|---|---|---|---|---|
| **A** | Lower `reconcileGrace` | 1 line | nothing | stale row 13 s → ~4 s |
| **B** | `serve` reads its own retained set at connect | serve | nothing | the correctness hole; stale row → ~1 pulse |
| **C** | Barrier-triggered reconcile | watch | 3 of the 4 inference mechanisms | stale row → ~50 ms |
| **D** | Roster topic, watch consumes it | serve + watch | all 4 | all of the above, plus an explicit membership statement |

**A** deserves stating because it is nearly free. The retained flood is measured at **under one
second** at every size tried (the measurement is in the module `CLAUDE.md`), against a 10 s grace.
Three seconds would take the observed 13 s to about 4. It fixes nothing else, simplifies nothing, and
the existing whole-host guard still covers a lost redelivery. If the only goal were the 13 seconds,
this is the change.

**B** is the one that is not optional. Nothing else addresses `serve` not knowing what it used to
run, and the consequence is orphaned retained topics with no owner — estate drift that no watch-side
change can clean.

**C and D are alternatives, not a sequence.** Both answer the same question by querying current
state. C asks the broker, D asks the host.

**Recommended: B + C**, holding D in reserve. Together they are two small changes, neither adds a new
source of truth, and between them they fix both confirmed problems. D is the fallback if C's ordering
assumption proves unreliable — see *Roster*.

---

## Barrier reconcile, planned — option C

The reconcile waits a fixed grace for a redelivery it forced, because nothing tells it when the
retained flood has finished. **Make the broker tell it.**

On a host restart transition the watch already calls `resubscribeHost`. Follow it with a publish to a
topic the watch itself subscribes to, carrying a nonce. When that message comes back, everything the
broker retained for the resubscribed filters has been delivered. Anything in the cache not seen since
the resubscribe is gone — definitively, not probably.

```
resubscribeHost(host)                       force redelivery
publish supervisor/watch/<client>/barrier   non-retained, QoS 0, nonce
… retained flood arrives …
barrier(nonce) returns                      the flood is complete
reap = cache.Services(host) - seen          no cutoff, no grace
```

**What it deletes:** `reconcileDelay`, `reconcileGrace`, the `connected` cutoff and the whole
`fromConnect` connect-versus-transition distinction, and `RecordCache.ServicesBefore`
(`metric_cache.go:510`) — replaced by a seen-set. The note "a reconcile is only ever scheduled beside
a redelivery" becomes structural rather than a rule to remember.

**What it does not delete, and this is the honest limit:** the whole-host reap guard stays. On a
vernemq release the store is flushed and the watch reconnects into an empty broker; the barrier would
return having seen nothing and reap every service on every host. Gating on the host being `online`
does not save it either — `forceRepublish` publishes the status **before** the record replay
(`engine.go:723-724`), so a watch acting on `online` races the replay it is waiting for. So the guard
survives: a reap that would empty a host holds once, resubscribes, and retries.

**Costs and caveats:**

- The watch must publish, which it does not today. One non-retained topic under
  `supervisor/watch/<client-id>/barrier`. Non-retained means `verify.sh` (which filters on the retain
  flag) never sees it, so no schema declaration and no drift rows.
- **MQTT does not guarantee this across topics.** §4.6 orders messages per topic from a given
  publisher; ordering between retained delivery on one filter and a later live publish on another is
  broker behaviour, not spec. VerneMQ serves a session from one FIFO queue over one TCP stream, so it
  holds in practice — but this must be **measured before it is relied on**, and the fallback must be
  a timeout that degrades to today's behaviour rather than to no reconcile at all.
- A late barrier from a superseded attempt must be ignored, hence the nonce.

---

## Serve readback, planned — option B

At connect, `serve` reconciles against **the union of its retained `+/name` topics and, if D is ever
built, its retained roster** — then tombstones every service the union names that config ∪ docker no
longer reports.

The subscribe already exists (`engine.go:629`) and already calls `RegisterService`. **Find out why it
found nothing on `may` before changing anything** — the handler only logs when `RegisterService`
returns bindings, so "no log" may mean "registered nothing" or "was never delivered". That
distinction decides whether this is a bug fix or a redesign.

With it working, the stale row resolves through the path that already exists: `serve` tombstones the
departed service, the watch removes it on the nil pulse in about one pulse. That is why B alone
mostly closes the visible symptom, and why C is about the remaining tail rather than the bulk.

---

## Roster, planned — option D, held in reserve

If C's ordering assumption does not hold, or the guard's survival is not acceptable, the host states
its membership instead.

`host/services_roster`, `valueKind` str, `persisted: false`, `pulseRule: Always()`, no `trendRule`
and no `trendFunc`, no display box, value being the sorted comma-joined `servicesByName` after the
ghost pass. Owned by `servicesProbe`, in `metrics()` and in a `newCacheMetricTask` in the host-scope
tail of `run()`. As a metric it inherits the record envelope, retained publish, topic template,
`metric.Topics()` declaration, schema leaf, `--log-subject` vocabulary and reconnect replay.

The discovery wildcard becomes a 1:1 swap — `topicDiscovery` → `topicRoster`, `onDiscovery` →
`onRoster` — which also collapses estate discovery from ~200 retained topics to 6. Three rules:
register names the cache lacks, evict-and-delete names the roster omits (then one `Refresh()`, since
`Delete` reindexes), ignore a roster stamped no later than the last applied for that host.

Published **retained at QoS 1**, unlike every other topic: `Store` skips notify on an equal value, so
an unchanged roster goes quiet until the 300 s heartbeat, and a lost roster change would strand the
watch for five minutes. Every other topic self-heals next tick. The subscribe side is already QoS 1
(`engine.go:373`).

**Where D beats C:** the vernemq-flush case resolves by construction, because a reap needs a roster
to act on and absence is never evidence — so the whole-host guard goes too, and all four inference
mechanisms with it. **Where C beats D:** no new source of truth, no estate-wide release, watch-only,
and a bug in the ghost pass cannot make a whole host's membership wrong at once. D concentrates on
one topic what is currently spread across ~200.

**Naming note.** The module's rules give `*_status` to booleans, `used_*` to consumption and
`failed_*` to counts. A roster is a fourth shape; `services_roster` is accepted rather than forced
into `*_status`, which would claim it is a boolean.

---

## The rewritten contract, planned

The acceptance test for whichever option lands. The doc comment on `RunListeningStreamLoop` is ~45
lines describing four interacting timers and cutoffs. Under **C** it should read roughly:

```
// On connect:
//  1. Forget the host status, the subscribed topics and any pending barrier.
//  2. Subscribe to every topic the cache already holds, in one packet.
//  3. Subscribe to discovery, to host status and to this client's own barrier topic.
//  4. Refresh the display.
//
// On a data message:
//  1. Ignore a topic the subscribed map does not hold, counting it as dropped.
//  2. Remove the service on an empty or nil pulse payload, being the tombstone a live host
//     publishes when a service departs.
//  3. Revive an offline host when the payload was published after the offline.
//  4. Ignore anything else from an offline host.
//  5. Stamp, store, and mark the service seen against any open barrier for its host.
//
// On host status:
//   - offline: evict every service to nil and store nil for the host metrics.
//   - online after an offline: resubscribe the host and open a barrier.
//   - online, unchanged: nothing.
//
// On a barrier:
//   - Reap every service of that host not seen since the resubscribe, unless that would empty the
//     host, in which case resubscribe and re-open the barrier once.
//
// On the purge tick: purge, resync, restore wildcards, revive, silence check, report.
```

Under **D** the barrier clauses become the roster's three rules and the guard clause disappears.

---

## Edge cases, worked

`C` / `D` marks where the two options differ.

| # | Case | Handled by |
|---|---|---|
| 1 | Membership signal arrives while its host is muted offline | Routes through `proveOnline` exactly as data does, so a wrongly-muted host recovers on the first payload stamped after the offline. Without this a mute is permanent. Applies to both. |
| 2 | A service the watch has never subscribed to | Register → subscribe → retained values delivered at subscribe. Values published before the subscribe are retained, after it are live. No gap either way. |
| 3 | Reaped service's records still in flight | The reap unsubscribes, so late records hit the subscribed-map check in `onData` and count as dropped. |
| 4 | vernemq store flushed by a release | **C**: barrier returns having seen nothing; the whole-host guard is what stops a total reap, and `forceRepublish` publishing status before its records (`engine.go:723`) is why gating on `online` does not substitute for it. **D**: no roster arrives, so nothing is reaped; resolves by construction. |
| 5 | Membership signal lost in transit | **C**: barrier lost → timeout fallback to today's behaviour. **D**: QoS 1, because an unchanged roster is not republished until the heartbeat. |
| 6 | Signal delivered out of order or superseded | **C**: nonce. **D**: timestamp guard against the last applied for that host. |
| 7 | `serve` SIGKILLed and restarted | Option B: reads its own retained set at connect and tombstones the difference. Neither C nor D covers this. |
| 8 | `serve` dies and stays dead | LWT → offline → watch evicts to nil and holds the slots; `Purge` deletes them after the window. Unchanged. |
| 9 | Watch suspends and wakes | `brokerRevive` probes or reconnects; a reconnect re-runs the connect path. **C** opens a barrier per host on the transitions that follow; **D** applies each retained roster on arrival. |
| 10 | Declared host that never publishes | Renders from its seeded nils; an unknown host counts as online so it still renders. Never discovered, never reaped. |
| 11 | Same service name on two hosts | Membership is per host and slots are per host. No interaction. |
| 12 | Malformed or reserved service name | **D** only: a roster is remote input, so validate non-empty, no `/`, not prefixed `ServiceNameSchema` (which `reindex` treats specially), and cap the count. **C** inherits today's per-topic parsing and needs nothing new. |
| 13 | More services than the display has rows | Unchanged — N rows and the `~` overflow marker, which already wins over every other cell state. |
| 14 | Local mode | `RunListeningProbesLoop` must grow no consumer of either mechanism, or the probe would read back its own answer. Under **D** the metric is produced by `servicesProbe` and ignored, and `RunAllProbesOnce` seeds it with every other ID; `verifyProbes()` panics in every mode, so the declaration is enforced locally too. |
| 15 | A service present with no values yet | A distinct display state, never a fault and never reaped. See *Phase 3*. |
| 16 | Multiple watches against one broker | **C**: barrier topic is keyed by client id. **D**: read-only, no interaction. |

---

## What gets deleted

Under **C**: `reconcileDelay`, `reconcileGrace` (`engine.go:902`), the `connected` cutoff variable
and the `fromConnect` distinction, `scheduleReconcile`'s cutoff bookkeeping, and
`RecordCache.ServicesBefore` (`metric_cache.go:510`) — replaced by a seen-set. **The whole-host guard
stays** (edge case 4). Under **D**, the guard and the remaining `hostReconcile` scaffolding go too.

**Kept either way, and none of it is reconcile machinery:** `proveOnline`, unchanged and load-bearing
(edge case 1); `resubscribeHost`, which keeps its revive-from-mute (`:153`) and restart (`:327`)
callers — the revive one matters because the watch discarded messages while it had the host muted and
`serve` never reconnected, so nothing republishes unprompted; `RecordCache.Purge`, which evicts on
**host** staleness via `hostLastSeen` (`metric_cache.go:423`) and has never been a per-service
reaper; the silence detector, `resyncTopics`, `subscribeWildcards`, and the offline eviction path.

**Surviving notes** from the current doc: the membership signal proves a host alive exactly as data
does; reaping is keyed by service name and never by slot; a subscribe is refused either by its token
or by a SUBACK return code above the maximum QoS; the display refreshes on connect and after a reap,
never per host and never per heartbeat; an unknown host counts as online.

---

## Phases

### Phase 0 — verify, planned

Two measurements, both before any design commitment.

1. **The blank.** Restart `serve` on a host with at least two ghost services while running a remote
   `watch` with `--log-subject=service/mlflow`, and compare against that host's own
   `retained [n] bytes at qos [0]` lines for the same service. The question is whether its value
   topics were published in the discovery pulse at all. If they were, retained delivery should have
   covered it and a mechanism is still unaccounted for; if they were not, the blank is publish-side
   and neither C nor D touches it.
2. **Barrier ordering.** Subscribe to a wildcard with a large retained set, publish a barrier, and
   confirm every retained message precedes it — repeatedly, at the sizes in the `CLAUDE.md`
   measurements (443 and 546 topics). If it does not hold on VerneMQ, C is out and D is the design.

### Phase 1 — hygiene, planned

1. **Sort the publish batch.** One `slices.SortFunc` by GUID in `Take` or at the `process` call site.
   Makes a pulse reproducible, which you want before reasoning about arrival ordering. Correctness
   does not depend on the resulting order (edge case 2) — it saves a round trip.
2. **Ghost derivations → `derivedInertf`.** A configured service with no container has nothing to
   sample and already says so; today seven of its metrics return `derivation{}` and log `unstated` at
   ERROR every pulse — 21 a pulse on `may`, 1638 in one uptime. `derivedInertf` also short-circuits
   rule evaluation, so a ghost stops being judged by a rule it cannot satisfy.

### Phase 2 — option B, planned

Diagnose and fix `serve`'s connect-time readback. Independent of everything else, and the only change
that addresses the correctness hole.

### Phase 3 — option C, planned

Barrier reconcile and the deletions above, gated on Phase 0's second measurement. If it fails, build
D instead; the edge-case table covers both.

### Phase 4 — the third row state, planned

With membership answered by a query rather than a timeout, the display can tell **present but not yet
reporting** from **measured and failed**. Today both render as a blank cell, and on the service grid
a failure also paints the service name in `colourAlert`, so a brand-new service looks broken. Render
the awaiting state neutral, keep `Failed` alert, and keep the existing precedence: sleeping wins over
failed, and the `~` overflow marker wins over both.

This is the reason to do the rest, and it is reachable after Phase 2 alone if Phase 0 shows the blank
is publish-side.

### Not doing

- **A deadline timer for the reconcile.** Worth 3 s of the 13 while the fixed grace exists; both C
  and D remove the grace, so it is moot. Recorded so it is not rediscovered.
- **Filling an empty row from the install tree.** A remote watch has no install tree, and it would be
  a second source of truth for the set this work exists to make singular.
- **Changing the `status` topic payload to carry membership.** Tempting — the topic exists, is QoS 1,
  is subscribed first at connect and already routes through `proveOnline` — but it is a bare
  `online`/`offline` string that health-check scripts match with `grep -q "^online$"`, and the LWT
  payload is fixed at connect so the will could never carry a live list.
- **A consumer of either mechanism in `RunListeningProbesLoop`.** Edge case 14.

---

## Estate note, built

The `10.200.1502` release moved several modules between `max` and `may` and the containers have not
followed. `max` is configured for cloudflare, grafana, letsencrypt, openra, supervisor while running
letsencrypt, mlflow, mlserver, supervisor; `may` is configured for influxdb3, mlflow, mlserver,
sonarr, supervisor, tempstat while running cloudflare, grafana, sonarr, supervisor, tempstat. Each
host therefore publishes a full record set for ~3 ghosts that live on the other, and `influxdb3` is
installed on `may` but not running, which is why `mad` drops every database write.

None of that is caused by this work and none of it is fixed by it. It is why the symptoms were
visible, and it should be resolved before Phase 0 is measured or the reproduction is confounded.
