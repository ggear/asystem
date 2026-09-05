# Watch stream contract

How a `watch` learns which services a host runs, why a departed service lingers, and what should
replace the machinery that currently compensates. Status is marked per section: **built** is in the
repo today, **planned** is not.

Read *Root cause* first — it is confirmed, it is two lines, and it changes which of the options below
are worth building. *Budget* is the latency target every option is measured against.

---

## Root cause, built

**On a graceful stop, `serve` mutes every watch and then sends tombstones the watch is guaranteed to
discard.** Both halves are in the code and each is deliberate on its own; together they are the bug.

`engine.go:686-697`, the shutdown defer:

```go
client.Publish(statusTopic, 1, true, hostStatusOffline).WaitTimeout(2 * time.Second)   // 1. offline
cache.Records(func(_ metric.RecordGUID, record *metric.Record) {
    if record.Topic != "" {
        client.Publish(record.Topic, 0, true, "")                                      // 2. tombstones
    }
})
```

`engine.go:166-173`, `onData`:

```go
if len(msg.Payload()) == 0 {
    if !online {
        dropCount.Add(1)
        return          // an empty payload from an offline host is dropped, and never proved online
    }
    rxCount.Add(1)
    removeService(guid)
```

The offline publish is `WaitTimeout`ed, so it is acknowledged before the tombstones are sent. The
watch therefore marks the host offline and drops every tombstone that follows. The watch's own doc
comment names this outcome as intended — *"Ignore anything else from an offline host, which is how a
departing host's own tombstones are left unread"* — and it is right to, because a shutdown tombstones
**every** topic, so honouring them would delete every row on every routine restart instead of
blanking them.

So on a graceful stop the tombstones accomplish nothing on the watch side. Their only lasting effect
is to **empty the broker's retained store**, which destroys the breadcrumbs the next process needs.
That is the second confirmed fault: `may` logged **zero** `rediscovered` lines on restart, and
`RunAllProbesPublishLoop`'s own note explains why that matters — *"The service name topic must be
retained, being the only breadcrumb a crash leaves behind ... the next process rediscovers the
service from that name, finds it absent from docker, and removes it, which is what finally clears the
broker."* The graceful path deletes exactly the breadcrumb the crash path depends on.

The 13 s `letsencrypt` row follows: nothing removed it, so the timed reconcile did — at
`reconcileDelay` (10 s) rounded up to the next `purgeInterval` (6 s), which is 10 s best case and 16 s
worst by construction.

**The second symptom is still unexplained.** `mlflow` was blank for one pulse while `mlserver`
painted, both ghosts on `may`. See *Phase 0*; nothing here assumes a mechanism.

---

## Budget and the latency chain

Pulse is 6 s and poll 3 s on a deployed host (`may`: `periodic [3000] ms poll`, `[6000] ms pulse`).
Target for a departed service to leave every watch: **within one pulse**, measured from the host
coming back online, since that is when the grid repaints and the stale row is visible.

**A tombstone does not wait for a pulse.** `RecordCache.Delete` calls `deletesListener.MarkDelete`
synchronously (`metric_cache.go:368-372`) and `serveDeletesListener.MarkDelete` publishes the empty
retained payload immediately (`engine.go:841-844`). So a removal detected in a poll is on the wire in
that poll. The publish path is not the constraint — **startup is**:

| Step | Cost on `may` today | Fix |
|---|---|---|
| broker connect → `online` published | ~0 | — |
| `databaseConnect` probes and backs off **before `RunPoll` starts** (`engine.go:704`) | 3.5 s observed with influx down, more on a longer outage | move it off the startup path |
| first ticker tick — `time.NewTicker` fires only after `PollMillis` (`probe.go:107`) | 3 s | run one tick immediately |
| readback lands, first poll that sees it evicts | ≤3 s | benign if late — costs one poll, never correctness |
| tombstone published | ~0 | — |

Measured on `may`: broker connect at `13:47:37`, first probe sample at `13:47:44` — **7 s of
startup before anything is published**, which alone breaks a 5 s budget regardless of what the
reconcile does. Fixing the two startup steps brings the whole chain to **≤3 s**, comfortably inside
one pulse, and makes every metric on every host appear 3-6 s sooner on every start as a side effect.

Running the readback *before* the first poll is a latency question, not a safety one: reconciling too
early simply finds nothing to remove and the next poll catches it. So no barrier or settle is needed
on the serve side — do not add one.

---

## The signal already has a recoverable form, and shutdown does not use it

`process` (`engine.go:750-756`) publishes a departure **twice**: first as nil-pulse JSON, then as an
empty payload.

```go
client.Publish(record.Topic, 0, true, payload)   // nil-pulse JSON — carries a timestamp
client.Publish(record.Topic, 0, true, "")        // empty — clears the retained store
```

That matters because the JSON form routes through `proveOnline` (`:181`) and is honoured even when
the watch has the host wrongly muted, whereas the empty form is dropped unconditionally.

**But the primary removal path never reaches `process`, and so emits only the unrecoverable form.**
`servicesProbe.poll` evicts then deletes in the same pass; `RecordCache.Delete` removes the dirty
entries (`metric_cache.go:346`) so the pulse never sees the nil record, and the only publish is
`MarkDelete`'s empty payload. `process`'s two-form branch covers only the interleave its own doc
comment describes — a record reaching the pulse still holding no pulse value.

So **both** departure paths publish an unrecoverable signal today, and A fixes only the shutdown one.
The fix is to give `MarkDelete` the same two forms: marshal a `metric.NewNilValue()` — which already
carries a fresh `Timestamp` (`metric_value_data.go:77-81`), which is all `proveOnline` needs — publish
it, then publish the empty payload. Three lines, and it makes the two removal paths identical instead
of subtly different. `MarkDelete` is called **after** `c.mutex.Unlock()` (`metric_cache.go:363`), so
this and the QoS change hold no lock across network I/O.

---

## Options

| | Change | Touches | Worst case | Fixes |
|---|---|---|---|---|
| **A** | Drop the shutdown tombstone-all | serve, ~6 lines deleted | — | the breadcrumb destruction; makes B possible |
| **B** | `serve` reconciles its retained set at connect | serve | ≤3 s once startup is unblocked | the departed service, at the source |
| **C** | Barrier-triggered reconcile | watch | ~50 ms | replaces the timed reconcile with a definitive one |
| **D** | Roster topic the watch consumes | serve + watch | ~50 ms | as C, plus an explicit membership statement |
| **E** | Lower `reconcileGrace` from 10 s to 3 s | 1 line | ~4 s | nothing else |

**A + B is the recommendation, and it meets the budget on its own.** They are one idea in two halves:
stop destroying the evidence, then act on it.

**A has one honest regression.** Today a graceful stop self-cleans the broker; after A a
decommissioned host leaves its retained data behind until the next vernemq recreate collects it. That
is acceptable because it is already the behaviour for a removed *module* (see the rename section in
the root `CLAUDE.md`), and because the alternative — tombstoning only departed services at shutdown —
is empty by definition, since at shutdown nothing has departed, the host is going away. A fresh watch
connecting while such a host is down may also briefly render stale values before the retained
`offline` lands and blanks them; that is today's post-crash behaviour becoming the normal case, not a
new failure mode.

- **A** deletes six lines. The offline status already tells every watch to blank the host, and
  `Purge` ages the records out, so tombstoning every topic on the way out is redundant for the watch
  and actively harmful for the next process. Removing it also means an empty payload only ever means
  *this one service departed* — never *I am going away* — so the two meanings the watch cannot
  currently separate stop being conflated.
- **B** then has something to read. At connect, `serve` registers its retained `+/name` topics; the
  first poll to see them finds each absent from config ∪ docker and evicts it, and the deletes
  listener publishes the tombstone in that same poll. **Worst case ≤3 s** once the two startup
  blockers above are removed, against ~7 s of startup alone today.

**C is the simplification, not the fix.** With A + B the departed service is gone in ≤3 s through
the path that already exists, so C buys the tail: a definitive answer in ~50 ms and the deletion of
`reconcileDelay`, `reconcileGrace`, the `connected` cutoff, the connect-versus-transition
distinction, and `RecordCache.ServicesBefore`. Worth doing for the contract it removes, not for the
seconds.

**D is held in reserve** for the one case C does not cover cleanly (edge case 7).

**E is recorded and not recommended.** It tunes the compensating mechanism rather than removing what
it compensates for, and A + B beat it on latency anyway.

---

## Recommendation tested against every case

Latency is the time from the departure becoming true to the row leaving every watch. `A+B` is the
recommendation; `+C` shows what the barrier adds.

| # | Case | A+B outcome | Latency | +C |
|---|---|---|---|---|
| 1 | Service moved to another host, `serve` restarted | Retained `+/name` survives (A); connect readback registers it (B); first poll evicts; pulse publishes both tombstone forms; watch removes | **≤3 s** | ~50 ms on the online transition |
| 2 | Container stopped, still configured | Becomes a ghost and stays — correct, it should show red, not vanish | n/a | unchanged |
| 3 | Container stopped and unconfigured | Next poll evicts and the deletes listener publishes in that poll | **≤3 s** | unchanged |
| 4 | `serve` SIGKILLed | Retained survives (unchanged by A); new process reads it back and reconciles | **≤3 s** | unchanged |
| 5 | `serve` stopped and never restarted | LWT → offline → watch evicts to nil and holds the slots; `Purge` deletes after the window | as today | unchanged |
| 6 | Watch wrongly muted the host when the tombstone was sent | Only once `MarkDelete` publishes the nil-pulse JSON form as well; that form carries a timestamp and routes through `proveOnline`. Without that change A does **not** close this case | **≤3 s** | barrier on the next transition |
| 7 | vernemq store flushed by a release | No retained anything; each `serve` republishes on reconnect | as today | **hazard** — the barrier returns having seen nothing and would reap every host. The whole-host guard must survive. Gating on `online` does not substitute: `forceRepublish` publishes the status *before* its records (`:723-724`), so a watch acting on `online` races the replay. **D** resolves this by construction |
| 8 | Tombstone packet lost (QoS 0) | Nothing removes it until the next `serve` restart | **unbounded** — see *Open* | barrier on the next transition, still unbounded between transitions |
| 9 | Watch suspends and wakes | `brokerRevive` probes or reconnects; a reconnect re-runs the connect path | as today | barrier per host on the transitions that follow |
| 10 | Watch starts fresh against a live estate | Retained set is complete (A stopped deleting it), so the first flood is the truth | ~1 s | barrier confirms it |
| 11 | Declared host that never publishes | Renders from seeded nils; unknown host counts as online so it still renders | n/a | never barriered, never reaped |
| 12 | Same service name on two hosts | Per host throughout — cache keys, slots, tombstones | n/a | barrier is per host |
| 13 | More services than display rows | Unchanged: N rows and the `~` marker, which already wins over every other cell state | n/a | unchanged |
| 14 | Local mode | Untouched. `RunListeningProbesLoop` has no broker and reconciles in the poll; A and B are both in `RunAllProbesPublishLoop` | 3 s | must grow no barrier — it would query the broker for an answer it already holds |
| 15 | Service present with no values yet | A distinct display state, never a fault and never reaped — see *Phase 4* | n/a | unchanged |
| 16 | Two watches against one broker | Read-only, no interaction | n/a | barrier topic keyed by client id |

**Cases 7 and 8 are where the recommendation is not yet bulletproof.** Both are addressed below.

---

## Where code drops silently

Every fault found here was a **drop with no counter and no log**, so the inventory is worth keeping.
`onData` is the disciplined one — four drop paths, all counted into `dropCount` and reported on the
purge tick (`engine.go:161-184`). The handlers around it are not:

| Site | Condition | Today |
|---|---|---|
| `onData` unknown topic | not in the subscribed map | counted |
| `onData` empty payload, host offline | **the root-cause drop** (`:167-170`) | counted, and never proved online, unlike the JSON branch |
| `onData` unmarshal failure | malformed payload | counted **and** logged ERROR — the only drop that names itself |
| `onData` not online, proveOnline fails | stale in-flight data | counted |
| `onDiscovery` unmarshal failure or nil pulse | `:271-274` | **silent return** |
| `onDiscovery` empty service name | `:276-278` | **silent return** |
| `onDiscovery` malformed topic, <6 tokens | `:279-282` | **silent return** |
| `onStatus` malformed topic, <3 tokens | `:299-301` | **silent return** |
| serve readback name handler | unmarshal failure or nil pulse (`:630-633`) | **silent return** |
| serve command handler | malformed topic | **silent return** |
| `process` marshal failure | record not published | logged ERROR |
| every retained publish | QoS 0, lost in transit | invisible everywhere |

**The serve readback's only failure mode is a silent return**, which is exactly why `may` produced no
evidence: the handler logs only when `RegisterService` returns bindings, so "no `rediscovered` line"
is indistinguishable between *was never delivered*, *failed to unmarshal*, *had a nil pulse* and
*registered nothing new*. **Diagnose that before changing it** — the four cases want different fixes,
and Phase 1 cannot start without knowing which one it is.

The rule worth adopting: **a drop is counted or logged, never both silent**. A malformed payload or a
short topic is a genuine fault somewhere and should not be indistinguishable from an empty broker.

---

## Robustness check against the documented rules

Checked against the lifecycle rules in the module `CLAUDE.md`. No conflicts, one strengthened:

- **"Every removal path must pair `Evict` with `Delete`"** — preserved. `servicesProbe.poll` already
  pairs them and `Delete` only removes records already evicted to nil.
- **"A host proves itself alive with traffic, not only with status"** — *strengthened*. Giving
  `MarkDelete` the JSON form means a tombstone can prove liveness exactly as data does, which is what
  closes case 6.
- **"Non-graceful exit self-heals via the *new* `serve`"** — *generalised*, and this is the strongest
  argument for A. Today the crash path leaves the retained set intact and is cleaned by the next
  process, while the graceful path deletes it and relies on tombstones the watch discards. After A
  there is **one** recovery path instead of two, and it is the one already proven.
- **"The reconcile is deferred, never a wipe"**, **"a heartbeat must not resubscribe"**, **"a
  reconcile is only ever scheduled beside a redelivery"**, **"refresh is connect-scoped"** — all
  untouched, since Phase 1 changes nothing in the watch.

Two implementation hazards found while checking, neither a design problem:

- **Moving `databaseConnect` off the startup path introduces a data race.** `db` is read by the pulse
  callback under a `db != nil` guard (`engine.go:785`) and would now be written by another goroutine,
  so it must become an `atomic.Pointer` or be mutex-guarded, and the `defer db.close()` at `:708`
  needs rehoming.
- **A docker hiccup cannot mass-tombstone.** If `p.services()` errors the poll returns before the
  removal loop; if docker returns an empty list without erroring, the ghosts built from
  `configuredServiceNames` keep the configured set alive and only unconfigured-but-running services
  would be removed. Existing behaviour, not introduced here, but it is what makes running the first
  tick immediately safe.

**Residual, and not a regression:** on a restart the departed service is repopulated from the
retained flood before the new process tombstones it, so its row appears and then vanishes ~3 s later
rather than never appearing. Today it also shows, from the watch's own cache, for 13 s. A + B
shortens the row's life; it does not prevent the row.

---

## Open: the two gaps

**Case 8, a lost tombstone, is the only unbounded one.** Departures are published at QoS 0 like
everything else, which is right for a value republished every pulse and wrong for a one-shot state
change. **Publish both tombstone forms at QoS 1.** They are rare — a handful a day estate-wide — and
the subscribe side is already QoS 1 for wildcards. That closes case 8 without a new mechanism and
brings its worst case in line with case 1.

**Case 7 is why C cannot delete the whole-host guard.** Keep the guard: a reap that would empty a
host holds once, resubscribes, re-opens the barrier, and only the retry reaps. That is the existing
behaviour and it is already proven against exactly this scenario. If keeping it is unacceptable, D is
the design that removes it by construction — a reap needs a roster to act on, and absence is never
evidence.

---

## Barrier reconcile, planned — option C

After `resubscribeHost` forces a redelivery, publish a nonce to a topic this watch also subscribes
to. When it returns, the retained flood for those filters is complete, so anything not seen since the
resubscribe is gone — definitively rather than probably.

```
resubscribeHost(host)                       force redelivery
publish supervisor/watch/<client>/barrier   non-retained, QoS 0, nonce
… retained flood arrives, names marked seen …
barrier(nonce) returns                      the flood is complete
reap = cache.Services(host) - seen          no cutoff, no grace, unless it would empty the host
```

Non-retained means `verify.sh`, which filters on the retain flag, never sees it — no schema
declaration and no drift rows. A superseded barrier is ignored by nonce.

**MQTT does not guarantee this across topics.** §4.6 orders messages per topic from a given
publisher; ordering between retained delivery on one filter and a later live publish on another is
broker behaviour, not spec. VerneMQ serves a session from one FIFO queue over one TCP stream, so it
should hold — but this is Phase 0's second measurement, and the fallback must be a timeout degrading
to today's behaviour, never to no reconcile at all.

---

## Roster, planned — option D, held in reserve

If C's ordering assumption fails, or the whole-host guard's survival is unacceptable, the host states
its membership instead: `host/services_roster`, `valueKind` str, `persisted: false`,
`pulseRule: Always()`, no `trendRule` and no `trendFunc`, no display box, value being the sorted
comma-joined `servicesByName` after the ghost pass. Owned by `servicesProbe`, in `metrics()` and in a
`newCacheMetricTask` in the host-scope tail of `run()`; as a metric it inherits the record envelope,
retained publish, topic template, `metric.Topics()` declaration, schema leaf, `--log-subject`
vocabulary and reconnect replay.

`topicDiscovery` → `topicRoster` and `onDiscovery` → `onRoster` is a 1:1 swap, collapsing estate
discovery from ~200 retained topics to 6. Three rules: register names the cache lacks, evict-and-
delete names the roster omits then one `Refresh()` (since `Delete` reindexes), ignore a roster
stamped no later than the last applied for that host. Published retained at **QoS 1**, because
`Store` skips notify on an equal value so an unchanged roster goes quiet until the 300 s heartbeat.

Validate on receipt — non-empty, no `/`, not prefixed `ServiceNameSchema` (which `reindex` treats
specially), and a count cap. A roster is remote input; per-topic discovery got this for free.

**Its cost** is a new source of truth: a bug in the ghost pass makes a whole host's membership wrong
at once, where today ~200 independent topics fail independently.

---

## What gets deleted

**A**: the six-line tombstone-all in the shutdown defer (`engine.go:689-694`) and the *"On shutdown"*
step 2 in the loop's doc comment.

**C**: `reconcileDelay`, `reconcileGrace` (`:902`), the `connected` cutoff and the `fromConnect`
distinction, and `RecordCache.ServicesBefore` (`metric_cache.go:510`), replaced by a seen-set. The
whole-host guard **stays** (case 7). Under **D** the guard and the remaining `hostReconcile`
scaffolding go too.

**Kept regardless, none of it reconcile machinery:** `proveOnline`, unchanged and load-bearing
(case 6); `resubscribeHost`, keeping its revive-from-mute (`:153`) and restart (`:327`) callers —
the revive one matters because the watch discarded messages while it had the host muted and `serve`
never reconnected, so nothing republishes unprompted; `RecordCache.Purge`, which evicts on **host**
staleness via `hostLastSeen` (`metric_cache.go:423`) and has never been a per-service reaper; the
silence detector, `resyncTopics`, `subscribeWildcards`, the offline eviction path.

**Surviving notes:** the departure signal proves a host alive exactly as data does; reaping is keyed
by service name and never by slot; a subscribe is refused either by its token or by a SUBACK return
code above the maximum QoS; the display refreshes on connect and after a reap, never per host and
never per heartbeat; an unknown host counts as online.

---

## How to test

**No services need moving, and none of it needs the estate.** Supervisor ships **no Python tests
today** — `src/test/python/` is empty — and Phase 1 is the reason to add a systest, because four of
its five steps are properties of the **running container** that a Go test cannot reach.

### Add a systest, planned

`src/test/python/system/system_test.py` plus a `.env_test`, following `src/mad/network` — which
connects to a broker at `127.0.0.1:${VERNEMQ_API_PORT}`, subscribes, and asserts payload shape. The
same pattern applies here, and it exercises what nothing currently tests: the packaged image, the
`cap_add`/`device_cgroup_rules`/bind-mount stanzas in `docker-compose.yml`, the generated
`check{alive,executing,healthy}.sh`, and the real SIGTERM shutdown path.

**`.env_test` must set `SUPERVISOR_HOST` to a host that appears in the generated `config.json`.**
The default is `host.docker.internal`, which matches no schema entry, so `config.Services(host)`
returns empty, there are no configured services, and the ghost and readback paths never exercise.
This is the same shape as tempstat's `.env_test`, which sets `TEMPSTAT_MOCK=1` and a null device map.

**Assert only what a container on a dev machine can actually measure.** The drive, sensor, mount and
kernel-log probes read the host's `/sys`, `/proc/mounts`, block devices and `/dev/kmsg`; under Docker
Desktop those are the VM's, not the Mac's, so they will fault or read inert. Assert the status topic,
the record envelope, and the host metrics that work anywhere — processor, memory, up time.

**The cost is real:** `fab st`, `fab t` and every `fab release` would then run it for this module.

#### Standard smoke tests first, following `network`

`src/mad/network/src/test/python/system/system_test.py` is the model, and its shape should be copied
before anything Phase-specific is added:

- **A warm-up retry loop.** The whole body runs inside `while not success and elapsed < TIMEOUT_WARMUP`
  (120 s), swallowing exceptions and retrying every second, because the container has to build, start
  and reach its first pulse. Supervisor needs a longer warm-up than network, not a shorter one — it
  polls at 3 s and pulses at 6 s, and the emulated-arch image is slow to boot under QEMU.
- **`test_publishes_vitals`.** Subscribe, wait for the topic set to arrive within `TIMEOUT`, then
  assert. For supervisor that set is:
  - `supervisor/<host>/status` is exactly `online`
  - `supervisor/<host>/data/host/used_processor` — a well-formed envelope, so
    `isinstance(timestamp, int)`, `pulse.ok` a bool, `0 <= pulse.value <= 100`, and the same for
    `trend`
  - `supervisor/<host>/data/service/supervisor/name` — supervisor sees its **own** container through
    the docker socket, which is the one service guaranteed to exist in this environment
- **`test_declares_every_published_topic`.** Walk `src/build/resources/schema/vernemq/model` for
  directories containing the `payload` leaf and assert every topic the test subscribed to is
  declared. Supervisor uses the same `payload` leaf name as network, so `_schema_topics()` copies
  verbatim. This is the systest-scale version of what `verify.sh` does against production, and it is
  the check that catches a metric renamed in `metric_build.go` without a `fab generate`.

Note the topics are host-scoped, so they are built from the `SUPERVISOR_HOST` that `.env_test` sets —
they cannot be constants the way network's `network/data/internet` is.

A fourth is worth considering and is not in any sibling module: **`docker exec supervisor
/asystem/etc/checkexecuting.sh`** returning 0. It is the script `install.sh` gates a deploy on, it is
generated, and nothing tests it. Use `checkexecuting` rather than `checkhealthy` — the latter asserts
data quality that depends on probes which cannot read a real host from here.

#### Then the Phase 1 assertions

| Step | Systest assertion |
|---|---|
| 1 | Bring the container up, let it publish, `docker stop`, then assert the host's retained data topics **still exist**. Better than the Go form — it exercises the real SIGTERM defer. |
| 2 | Publish a retained `supervisor/<host>/data/service/zztest/name`, restart the container, assert the topic is cleared within one pulse. The most realistic form of this test — real `config.json`, real docker socket. |
| 3 | Subscribe before triggering the removal, assert both forms arrive and the retained topic ends cleared. |
| 4 | Natural fit — the systest has no influxdb3, so asserting the pulse still publishes *is* the offline-database case. |
| 5 | Time from container start to the first retained data topic appearing. The end-to-end form of the log timing below. |

### In Go, against a throwaway broker

`TestEngine_RunListeningStreamLoop` already spins up a real VerneMQ per test via
`testutil.SetupBrokerContainer(t)` behind `testutil.RequiresDocker(t)`. Keep the **fine-grained
logic** here — it is faster, it runs without an image, and it can reach states the container cannot
be steered into. Each assertion below fails against today's code, which is what makes them
regression tests rather than descriptions:

| Step | Test |
|---|---|
| 1 | Run the publish loop, cancel it, assert the host's retained data topics **still exist**. Today they are gone. |
| 2 | Pre-publish a retained `supervisor/<host>/data/service/zztest/name`, start the loop, assert the service registers and is tombstoned within a poll. |
| 3 | Subscribe, trigger a delete, assert **two** messages arrive — nil-pulse JSON then the empty payload — and that the retained topic ends up cleared. |
| 4 | Assert a nil database client does not panic under a concurrent pulse — the race the `atomic.Pointer` exists for, which the systest cannot provoke. |
| 5 | Assert the first pulse callback fires within a few hundred ms of start rather than after `PollMillis`. |

The division is: **the systest proves the container behaves, the Go tests prove the logic does.**
Case 6 in particular — a tombstone arriving while the watch has the host wrongly muted — belongs in
Go, because muting a host on demand is a state the systest has no way to create.

### On a host, with one synthetic topic

**The estate cannot produce the orphan condition naturally right now** — on `max`, config ∪ running
covers all seven retained service names, so nothing is orphaned. Create it deliberately:

```bash
mosquitto_pub -h "$VERNEMQ_SERVICE_PROD" -p "$VERNEMQ_API_PORT" -u supervisor -P "$VERNEMQ_TOKEN" \
  -r -t 'supervisor/macmini-max/data/service/zztest/name' \
  -m '{"timestamp":'"$(date +%s)"',"pulse":{"ok":true,"kind":4,"valueString":"zztest"},"trend":{"ok":true,"kind":4,"valueString":"zztest"}}'
```

Restart supervisor on that host and watch. **Today** a `zztest` row appears on every watch and
survives until the reconcile reaps it at 10-16 s. **After Phase 1** the new process rediscovers it,
finds it in neither docker nor config, and tombstones it within ~3 s. Clear it afterwards with
`-r -n` on the same topic. One topic, obviously named, fully reversible — and the phantom row it
produces is itself the demonstration.

### Steps 4 and 5 need no setup

Read the serve log and time `sessions [broker] connect` against the first `gathered [n] metrics`
line. That gap is 7 s on `may` today and should fall to under a second.

### Caution on `fab exe`

`BROKER_HOST` resolves to `host.docker.internal`, so a local run cannot touch the production broker.
But `SUPERVISOR_HOST` is also `host.docker.internal`, which matches no schema entry, so
`config.Services(host)` is empty, there are no configured services and the ghost path never
exercises. Fine for checking a mechanism, not representative of a host.

---

## Phases

### Phase 0 — verify, planned

1. **The blank.** Restart `serve` on a host with at least two ghost services while running a remote
   `watch` with `--log-subject=service/mlflow`, against that host's own `retained [n] bytes at qos
   [0]` lines for the same service. The question is whether its value topics were published in the
   discovery pulse at all. If they were not, the blank is publish-side and no option here touches it
   — fix it there. If they **were**, retained delivery should have covered it and a mechanism is
   unaccounted for; that becomes its own investigation, and until it is understood Phase 4 only masks
   the symptom by rendering the state honestly rather than removing it.
2. **Barrier ordering**, only if C is wanted. Subscribe to a wildcard with a large retained set,
   publish a barrier, confirm every retained message precedes it, repeatedly, at the sizes already
   measured in `CLAUDE.md` (443 and 546 topics). If it does not hold on VerneMQ, C is out and D is
   the design.

### Phase 1 — A + B, planned

Seven changes — five in `RunAllProbesPublishLoop`, `RunPoll` and the deletes listener, plus the
module's first systest and the doc updates. **None in the watch.**

1. **Delete the shutdown tombstone-all** (`engine.go:689-694`).
2. **Instrument the readback's four silent returns**, then fix whatever they reveal.
3. **Give `MarkDelete` both tombstone forms and publish them at QoS 1** — the JSON form closes
   case 6, QoS 1 closes case 8, and the two removal paths stop differing.
4. **Move `databaseConnect` off the startup path** (`:704`), which costs 3.5 s before a single metric
   is sampled when influx is down, and more on a longer outage.
5. **Run the first poll tick immediately** rather than after `PollMillis` (`probe.go:107`).
6. **Add the systest and its `.env_test`** — see *How to test*. It is where steps 1, 2, 3 and 5 are
   asserted, and it is the module's first Python test of any kind.
7. **Update the two doc comments that currently contradict each other** — `RunAllProbesPublishLoop`'s
   *"On shutdown ... 2. Publish an empty payload for every retained topic"* and the watch's *"Ignore
   anything else from an offline host, which is how a departing host's own tombstones are left
   unread"* — plus the *Service slots & lifecycle across restarts* section of the module
   `CLAUDE.md`, where the crash path is described as the exceptional one. After A it is the only one.

Together: **≤3 s worst case**, inside one pulse, and cases 1, 3, 4, 6 and 8 closed. Steps 4 and 5
also make every metric on every host appear several seconds sooner on every start.

**Step 6 earns its place beyond Phase 1.** Supervisor carries more unusual container configuration
than any other module here — `SYS_ADMIN` and `SYS_RAWIO`, `device_cgroup_rules` for `/dev/kmsg` and
block devices, the `/` bind at `$SUPERVISOR_MOUNT`, the `/etc/fstab` and `/dev` binds, `rshared`
propagation for `/share` and `/backup` — and none of it has a test. The systest is the only thing
that would catch a regression in the image, the compose stanzas or the generated health-check
scripts, all of which are invisible to the Go suite.

**Step 2 is the keystone, not the optional one.** Step 1 makes the breadcrumbs survive, but if the
readback is broken nothing reads them, the new process never tombstones the departed service, and the
13 s reconcile catches it exactly as today — no harm, but no observable improvement either. The
minimal set that changes anything is **1 + 2 + 3**, and its size is dominated by whatever step 2's
diagnosis turns up. Steps 4 and 5 are genuinely separable and can land first on their own.

**Do Phase 2 first if the readback diagnosis is not immediately obvious.** The ghost `unstated` ERROR
storm is 21 lines a pulse on `may`, which is what you would be reading through.

**Effort.** Test coupling is light — three references to the changed functions across two test files.

| Step | Size | Risk |
|---|---|---|
| 1 delete tombstone-all | ~6 lines deleted | low, pure deletion |
| 3 `MarkDelete` two forms + QoS 1 | ~5 lines | low, runs outside the cache mutex |
| 5 first tick immediate | ~5 lines | low-med, must not disturb `pulseTickCount`/`heartbeatPulseCount` |
| 4 `databaseConnect` async | ~15 lines | med, needs `atomic.Pointer` and the `defer db.close()` rehomed |
| 6 systest + `.env_test` | ~150 lines, new to this module | med — first `fab st` for supervisor, may surface image or compose issues |
| 7 doc comments and `CLAUDE.md` | prose | low but slow at this repo's standard |
| 2 readback | ~10 lines to instrument, **fix unknown** | **unknown** |

Steps 1, 3, 4 and 5 are about a day together; step 6 half a day to a day, since a module's first
systest usually surfaces something about the image; step 7 another half day. **The schedule
driver is not the coding** — supervisor is group 31 and deploys to every host, so step 2's diagnosis
and the acceptance criteria below both need real releases to observe. Two releases minimum: one to
get the instrumentation onto a host, one to validate the fix.

**Acceptance, on the next real release:** a departed service leaves every watch within one pulse; a
`rediscovered` line appears on the restarting host; and the reconcile's `reclaims` line does **not**
fire for that host. The third is the one that matters — it is the evidence for the decision below.

### Phase 2 — hygiene, planned, independent

1. **Sort the publish batch.** `RecordCache.Take` builds its slice by ranging a map
   (`metric_cache.go:594`) and `process` consumes it in that order, as does the `forceRepublish`
   replay, so a pulse is non-deterministic. One `slices.SortFunc` by GUID makes it reproducible,
   which you want before reasoning about arrival ordering.
2. **Ghost derivations → `derivedInertf`.** A configured service with no container has nothing to
   sample and already says so; today seven of its metrics return `derivation{}` and log `unstated` at
   ERROR every pulse — 21 a pulse on `may`, 1638 in one uptime. It also short-circuits rule
   evaluation, so a ghost stops being judged by a rule it cannot satisfy.

### Phase 2.5 — decide whether the reconcile still earns its place, planned

**This decision is not answerable today**, which is the real reason Phase 1 comes first: the reconcile
is currently compensating for two bugs, so of course it fires. After Phase 1 it should be
compensating for almost nothing, and the gate is evidence rather than judgement.

Leave it in place, raise its `reclaims` line to a level you will notice, and watch across a month of
releases and restarts:

- **It never fires** → it is dead weight. Delete it, and Phase 3 is unnecessary: the departure path
  alone is sufficient and there is nothing left to simplify.
- **It fires occasionally** → each firing is a departure that got lost. Diagnose it; that is the
  case Phase 3 or D would need to handle, and knowing which case it is decides between them.
- **It fires routinely** → Phase 1 did not work and none of what follows should be built on it.

### Phase 3 — C, planned, optional

Barrier reconcile and its deletions, gated on Phase 0's second measurement. Do it for the contract it
removes, not for the latency, which Phase 1 already delivers.

### Phase 4 — the third row state, planned

Distinguish **present but not yet reporting** from **measured and failed**. Today both render as a
blank cell and a failure also paints the service name in `colourAlert`, so a brand-new service looks
broken. Render the awaiting state neutral, keep `Failed` alert, and keep the existing precedence:
sleeping wins over failed, and the `~` overflow marker wins over both. Reachable after Phase 1.

### Not doing

- **Filling an empty row from the install tree.** A remote watch has no install tree, and it would be
  a second source of truth for the set this work exists to make singular.
- **Honouring empty-payload tombstones from an offline host.** The reason they are dropped is sound;
  the fix is A, which stops sending the ambiguous ones, plus the nil-pulse JSON form that already
  proves online.
- **Changing the `status` payload to carry membership.** Tempting — one topic, QoS 1, subscribed
  first at connect, already routed through `proveOnline` — but it is a bare `online`/`offline` string
  that health checks match with `grep -q "^online$"`, and the LWT payload is fixed at connect so the
  will could never carry a live list.
- **A barrier or roster consumer in `RunListeningProbesLoop`.** Case 14.

---

## Estate note, built

The `10.200.1502` release moved modules between `max` and `may` and the containers have not followed.
`max` is configured for cloudflare, grafana, letsencrypt, openra, supervisor while running
letsencrypt, mlflow, mlserver, supervisor; `may` is configured for influxdb3, mlflow, mlserver,
sonarr, supervisor, tempstat while running cloudflare, grafana, sonarr, supervisor, tempstat. Each
host publishes a full record set for ~3 ghosts that live on the other, and `influxdb3` is installed on
`may` but not running, which is why `mad` drops every database write.

None of that is caused by this work or fixed by it. It is why the symptoms were visible, and it should
be resolved before Phase 0 is measured or the reproduction is confounded.
