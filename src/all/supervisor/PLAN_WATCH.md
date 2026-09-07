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

## Recommendation tested against every case, A + B built

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

## Open: the two gaps — one closed, one deliberately kept

**Case 8 is closed, built.** Both tombstone forms now publish at **QoS 1**, in both removal paths.
The reasoning below is why, and is kept because the temptation to put them back on QoS 0 with
everything else will recur.

**Case 8, a lost tombstone, was the only unbounded one.** Departures were published at QoS 0 like
everything else, which is right for a value republished every pulse and wrong for a one-shot state
change. They are rare — a handful a day estate-wide — and the subscribe side is already QoS 1 for
wildcards, so this closed case 8 without a new mechanism and brought its worst case in line with
case 1.

**Case 7 is why C cannot delete the whole-host guard, and none of this changes it.** Keep the guard:
a reap that would empty a host holds once, resubscribes, re-opens the barrier, and only the retry
reaps. That is the existing behaviour and it is already proven against exactly this scenario. If keeping it is unacceptable, D is
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
should hold — but this is Phase 0's second measurement.

**The fallback is skip-and-retry, not degrade-to-timer.** This paragraph used to say the fallback "must
be a timeout degrading to today's behaviour, never to no reconcile at all". **That is now rejected**, and
the reasoning is recorded because the degrade reading is the intuitive one and will be reached again.
On a barrier that does not return, hold the reap, re-open the barrier, resubscribe and reschedule; only
the retry reaps, and after a bounded number of failed barriers warn loudly and reap nothing for that
host. That is not a new mechanism — it is the shape the **whole-host guard already uses** (`engine.go`'s
retry branch), applied to a second trigger, and already proven against case 7.

Four reasons, strongest first:

- **The two failure modes are not symmetric.** The reconcile is a backstop for a *lost departure*, and
  Phase 1 exists to stop departures being lost — `mad` fired it zero times in 14.5 hours. Skipping means
  failing to clean up something that almost never needs cleaning. Degrading means deleting a live row on
  a 10 s guess. Against a backstop for a rare event, wrongly acting is the worse error.
- **Degrading goes to a *less*-evidenced answer, not a safer one.** A barrier fails to return when the
  publish was lost mid-flight, the subscribe was refused (`0x80`, which vernemq really does seconds into
  a recreate), the QoS 0 message was dropped, or the connection died — **and every one of those is also a
  condition under which the retained flood did not complete.** So the moment the barrier says "the
  evidence is missing" is exactly the moment you would hand the decision to a timer whose whole premise
  is that ten seconds was surely enough. The timer never had evidence; it just cannot tell.
- **Degrading means C deletes nothing.** `reconcileDelay`, `reconcileGrace`, `started`, `connected`,
  `fromConnect`, `ServicesBefore`, the wall/monotonic split and the second-granularity fuzz all survive
  as the fallback path, so C is purely additive and gains a second reconcile path to interact with. The
  timed arm then becomes permanently dormant code exercised only in rare failure, which can never be
  retired because it can never be proven unused.
- **Skipping is countable, degrading is silent.** A skip emits a WARN, so "never fires" is evidence the
  barrier is sound and "fires often" is immediate evidence it is not. A silent degrade has to be logged
  to be known, and once it is logged, acting on it buys nothing.

**On the fear the old wording encoded**, two things blunt it. `RecordCache.Purge` already evicts on
**host** staleness via `hostLastSeen`, so a genuinely dead host still clears; what a skipped reap leaves
is a stale *service* on a *live* host. And skip-and-retry means no reap **now**, not no reap ever.

**Do not settle this before the shadow data.** If `shadowed [pending]` turns out to be common, the
barrier does not reliably return in production, and **neither fallback saves C** — that is a reason not
to build it rather than a reason to pick a fallback. Treat the above as the fallback *if* C is built.

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

### Add a systest, built

**What it ended up being: 15 cases in 139 s**, in this order, because the mutating cases must not run
ahead of the read-only ones. The stop-plant-restart-rediscover-tombstone cycle is half the runtime on
its own (68 s, nearly all container boot); nothing else exceeds 13 s.

| Case | Asserts |
|---|---|
| `publishes_vitals` | status is `online`, two host envelopes are well formed and in range, and supervisor sees its own container |
| `reports_an_unmeasurable_metric_as_failed_and_an_absent_one_as_inert` | temperature carries `failed`; the fan and the kernel log read 0 and ok without it |
| `logs_an_environment_fault_at_warn_and_a_host_fact_at_info` | the levels — `errEnvironment` at WARN, the sensor tier at INFO, neither at ERROR |
| `reports_a_ghost_and_an_unconfigured_service` | a configured service with no container reads not ok and still publishes its name; a running service absent from the config reads not ok |
| `declares_every_published_topic` | every topic published for the host and its configured services is declared under `model/`, which is what catches a metric renamed without a `fab generate` |
| `passes_its_own_health_check` | `docker exec … checkexecuting.sh` exits 0 |
| `never_panics_and_stays_healthy` | docker reports `healthy`, and no `panic:` or goroutine dump in the logs |
| `reports_a_declared_share_that_never_mounts_as_failed` | the one *positive* failure the fixture drives — a share in `fstab` with no `proc/mounts` line reads **100 and not ok** after `mountSettle`, and carries no `failed`, since not-mounted is countable rather than unmeasurable |
| `removes_a_service_that_departs` | a retained orphan name is tombstoned in both forms, the nil form carries a stamp, and the topic ends cleared |
| `retains_its_records_across_a_graceful_stop` | after `docker stop` the status is `offline` **and** the data topics survive |
| `rediscovers_and_clears_an_orphan_on_restart` | an orphan planted while the host is down is read back and tombstoned after `docker start` |
| `registers_a_service_that_appears_and_removes_one_that_goes` | a **real container** started and removed on the docker socket — the service appears and is published, then is tombstoned in both forms. This is production scenarios 1 and 2 for the serve half, and it is stronger than the planted-retained-topic case because nothing is simulated |
| `resumes_publishing_after_the_broker_restarts` | `docker restart vernemq`, then the host re-asserts `online` **and** publishes a value stamped after the restart — a retained value proves nothing here, only a fresh one does |
| `publishes_its_will_and_keeps_its_records_when_killed` | `docker kill`, then the broker's last will marks the host offline while every retained record survives — the crash path, and the half that distinguishes the will from the graceful publish |
| `retained_delivery_precedes_a_barrier_published_after_the_subscribe` | the Phase 2 measurement |

**Subscribe before you trigger.** The departure path is now fast enough to finish between a publish
and a second client's connect, so a test that published first saw *nothing at all* — which reads as a
failure and is the fix working. `_await` takes an `on_ready` callback that fires from the connect
handler, and both the departure and the restart cases use it.

`src/test/python/system/system_test.py` plus a `.env_test`, following `src/mad/network` — which
connects to a broker at `127.0.0.1:${VERNEMQ_API_PORT}`, subscribes, and asserts payload shape. The
same pattern applies here, and it exercises what nothing currently tests: the packaged image, the
`cap_add`/`device_cgroup_rules`/bind-mount stanzas in `docker-compose.yml`, the generated
`check{alive,executing,healthy}.sh`, and the real SIGTERM shutdown path.

**`.env_test` must set `SUPERVISOR_HOST` to a host that appears in the generated `config.json`.**
The default is `host.docker.internal`, which matches no schema entry, so `config.Services(host)`
returns empty, there are no configured services, and the ghost and readback paths never exercise.
This is the same shape as tempstat's `.env_test`, which sets `TEMPSTAT_MOCK=1` and a null device map.

#### It would not start as configured, measured on Docker Desktop

Tested directly on the dev machine (`Docker Desktop`, `7.0.12-linuxkit`). All of it is resolved by the
parameterisation below, plus two things this table did not predict — see *Deviations*: the image ships
no binary at all, and the `/dev` bind's target must move out of the data directory or `fab clean` fails.

| Stanza | Result | Blocker |
|---|---|---|
| `propagation: rshared` on `/share` and `/backup` | `path /host_mnt/private/tmp is mounted on /host_mnt/private but it is not a shared mount` | **yes, hard failure** |
| `/etc/fstab:/etc/fstab:ro` | `/etc/fstab` does not exist on macOS; the bind would create a directory under the Mac's `/private/etc` | **yes** |
| `/:/${SUPERVISOR_MOUNT}:ro` | mounts, but `ls` returns **only `Users`** — Docker Desktop exposes the shared paths, so `/host/proc`, `/host/sys`, `/host/dev` and `/host/var/lib/asystem/install` do not exist | no, but every probe reading through the mount finds nothing |
| `/var/lib/btrfs`, `/var/lib/asystem/install`, `/home/asystem` | absent on macOS; compose would auto-create them at the Mac root | no, but it pollutes the machine |
| `cap_add` `SYSLOG`/`SYS_RAWIO`/`SYS_ADMIN`, `device_cgroup_rules`, `apparmor=unconfined` | accepted, container runs | no |
| `/var/run/docker.sock` | works, special-cased by Docker Desktop | no |

#### Parameterising the host-coupled stanzas

Compose interpolates scalars from the generated `.env`, the same mechanism `${SERVICE_DATA_DIR}` and
`${SUPERVISOR_MOUNT}` already use. Because every variable below is always defined in `.env_all`, none
needs the `${VAR:-default}` form the root `CLAUDE.md` records as unsafe.

| Variable | `.env_all` (production, unchanged) | `.env_test` / `.env_exec` |
|---|---|---|
| `SUPERVISOR_ROOT_SOURCE` | `/` | `./target/runtime-system/host` |
| `SUPERVISOR_FSTAB_SOURCE` | `/etc/fstab` | `./target/runtime-system/host/etc/fstab` |
| `SUPERVISOR_BTRFS_SOURCE` | `/var/lib/btrfs` | `./target/runtime-system/host/var/lib/btrfs` |
| `SUPERVISOR_INSTALL_SOURCE` | `/var/lib/asystem/install` | `./target/runtime-system/host/var/lib/asystem/install` |
| `SUPERVISOR_HOME_SOURCE` | `/home/asystem` | `./target/runtime-system/host/home/asystem` |
| `SUPERVISOR_SHARE_SOURCE` | `/share` | `./target/runtime-system/host/share` |
| `SUPERVISOR_BACKUP_SOURCE` | `/backup` | `./target/runtime-system/host/backup` |
| `SUPERVISOR_DEV_SOURCE` | `/dev` | `./target/runtime-system/host/dev` |
| `SUPERVISOR_DEV_TARGET` | `/dev` | `/asystem/mnt/dev` |
| `SUPERVISOR_BIND_PROPAGATION` | `rshared` | `rprivate` |

**`/dev` is the one that needs its target parameterised as well.** Every other bind can point its
source at a throwaway directory and keep its target, but mounting an empty directory over the
container's own `/dev` removes `/dev/null`, `/dev/urandom` and the rest, and the container will not
run. The bind exists for `mount(8)` in the backup stages — which are dormant — so moving the target
aside under test costs nothing. Note the probes already read block devices through the **rebased**
path under `${SUPERVISOR_MOUNT}`, not through this bind.

**`.env_exec` needs the same values as `.env_test`, not just `.env_test`.** `_write_env` layers
exactly one environment file over `.env_all` — `.env_prod` on a release, `.env_test` for `fab st`,
`.env_exec` for `fab exe` — and there is no shared dev file, so a value set only in `.env_test`
leaves `fab exe` on the production paths and failing exactly as today. The root `CLAUDE.md` records
this trap; supervisor currently has neither file.

**`create_host_path: true`** already appears on the `/share` and `/backup` binds and should be
carried onto the parameterised ones. But prefer a **committed fixture tree** at
`src/test/resources/host/` over auto-created empty directories, and point `SUPERVISOR_ROOT_SOURCE`
and `SUPERVISOR_FSTAB_SOURCE` into it — `src/test/resources/` is where this repo puts fixtures, the
tree must exist *before* `fab st` brings the container up, and a committed tree is reviewable.

#### The dummy tree is the negative-path fixture, and that is the best part

Supervisor's documented contract is that a metric which cannot measure its input **says so** rather
than reporting a confident zero — *inert* (value 0, `ok` true, derivation ending "so the metric is
inert and always ok") where there is genuinely nothing to measure, *errored* (`failed` set, value
blanked, WARN under `errEnvironment`) where the input should exist and did not. **Those paths are
today exercised only in production, when something is already broken.** A synthetic `/host` tree
exercises them on demand, which is worth more than the Phase 1 assertions.

Build **one** tree that deliberately supplies some inputs and omits others, so a single run asserts
both directions:

| Planted in the fixture | Probe | Expected |
|---|---|---|
| `sys/class/hwmon/hwmon0/{name,temp1_label=Package id 0,temp1_input=45000}` | `host/temperature` | reads 45 °C, tier logged **INFO** once at discovery |
| *no* `fan1_input` anywhere | `host/spin_fan_speed` | **inert** — 0, ok true, "the metric is inert and always ok" |
| `sys/class/net/eth9/{device→.,speed=1000,statistics/{rx,tx}_bytes}` | `host/used_network` | `errProbeWarmingUp` on the first poll at **DEBUG**, a rate thereafter |
| *no* `device` symlink on any interface | — | if the symlink is omitted instead: **inert**, 0, ok, reason in the derivation |
| `etc/fstab` declaring `/share/10` with no matching `proc/mounts` line | `host/failed_shares` | counts it failed after `mountSettle` (**2 min**) and goes red — the one *positive* failure assertion |
| `proc/mounts` with an `ext4` line for `/` | `host/used_home_space` | reads a percentage |
| *no* `proc/mounts` at all (variant) | — | `mountBase` falls back to `mountBareRoot` and logs the base choice at INFO; the documented fallback, otherwise never tested |
| *empty* `var/lib/asystem/install` | `host/allocated_memory` | **errored** — "none of the [n] configured services are installed", `errEnvironment`, **WARN**, not-ok |
| `var/lib/asystem/install/<svc>/latest/{.env,docker-compose.yml}` | same | reads a ceiling, and the `examined` line names it |
| *no* `dev/kmsg` | `host/failed_log_messages` | warns **once**, reports 0, and does **not** error — an error would redden every host |

Four assertions matter more than the individual readings:

1. **No metric reports a confident zero for an input it could not read.** Every metric is either
   inert-and-ok or carries `failed` — never zero-and-ok when it failed.
2. **The levels are right.** `errEnvironment` at WARN, permanent host facts (no fan, no SMART, sensor
   tier) at INFO, code faults at ERROR. Assert by grepping `docker logs supervisor` for the metric's
   subject and level; the log layout is already pinned by `go/ast` tests, so this is stable.
3. **Nothing panics and the container stays healthy.** Verified from the fragment:
   `checkhealthy.sh` asserts `.pulse.ok != null` and a timestamp under 1200 s, plus the docker ping —
   **not** that any metric is green. So a host where most probes fault still passes its health check,
   and the systest will not fail for the wrong reason.
4. **`failed_shares` proves a metric can go red**, not merely inert. It is the only fixture that
   drives a genuine failure, which is why it earns its cost — and the cost is real: `mountSettle` is
   **2 minutes**, so that assertion needs a warm-up well past network's 120 s, or its own slow test.

**This weakens one of the reasons for the systest, and the plan should say so.** The argument that it
would cover the image, the `cap_add`/`device_cgroup_rules`/bind stanzas and the propagation modes
mostly evaporates, because the systest has to strip exactly the unusual parts to run at all. The
capabilities and device rules are still exercised; the binds and propagation are not. What survives
intact is the smoke tests, the generated health-check script, and every Phase 1 assertion — those
depend only on the broker and the docker socket, both of which work.

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
  declared — and it goes further than network's, asserting every topic actually *published* for the
  host and its configured services rather than a hand-listed few. Supervisor uses the same `payload`
  leaf name, so the walk is network's, inlined at its one call site. This is the systest-scale version
  of what `verify.sh` does against production, and it is the check that catches a metric renamed in
  `metric_build.go` without a `fab generate`.

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

### In Go, against a throwaway broker, built

`TestEngine_RunListeningStreamLoop` already spins up a real VerneMQ per test via
`testutil.SetupBrokerContainer(t)` behind `testutil.RequiresDocker(t)`. Keep the **fine-grained
logic** here — it is faster, it runs without an image, and it can reach states the container cannot
be steered into. Each assertion below was run once with its fix reverted and observed to fail, which
is what makes them regression tests rather than descriptions:

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

### Steps 4 and 5, measured

Read the serve log and time `sessions [broker] connect` against the first `gathered [n] metrics`
line. That gap was 7 s on `may`. In the Go test the first retained publish lands at **2.05 s** against
**5.06 s** with the immediate tick removed, while the unreachable database backs off for 3.5 s on its
own goroutine without delaying it — so the remaining 2 s is the first docker poll, not dead time.

### `fab exe`, resolved

`BROKER_HOST` resolves to `host.docker.internal`, so a local run cannot touch the production broker.
`SUPERVISOR_HOST` used to resolve there too, which matches no schema entry, so `config.Services(host)`
was empty, there were no configured services and the ghost path never exercised. `.env_exec` now sets
it to a host that **is** in `config.json`, and carries the same values as `.env_test` — which it must,
since `_write_env` layers exactly one environment file and there is no shared dev file. A `fab exe` is
therefore representative enough to read a dashboard against, and it is the fast iteration loop for the
systest: bring the stack up once, then run `pytest` against it repeatedly.

---

## Deviations from this plan, built

Recorded as they were made, with the reason, so the plan and the repo do not disagree silently.

- **Phase 1 step 10 was inverted: ghost derivations are stated, not inert.** The plan asked for
  `derivedInertf`, arguing a ghost "stops being judged by a rule it cannot satisfy". That would have
  turned every ghost **green**: six of the seven affected metrics carry
  `All(Gated(GateServiceAggregate), ...)` and the seventh, `health_status`, is `Truthy()` on a value
  that is `false` — and `evaluateRule` short-circuits an inert metric to `OK: true` before either is
  read, so the very rules that paint a ghost red would never have been evaluated. A configured service with no container is a fault the display must
  show, not an absence like a fanless host. The `unstated` ERROR storm is fixed by the half that
  actually caused it — the empty `derivation{}` — so each ghost metric now states one
  (`computed [0 pct] absent, service [x] is configured with no container ...`) and the rule still runs.
  Inert stays for the four host cases where there is genuinely nothing on the host to measure.
- **The image now builds its own Go binary, because supervisor could not run locally at all.** The
  plan assumed step 7 only had to strip the host-coupled binds. It does not: supervisor's `Dockerfile`
  ships **no binary** and its `CMD` is `/asystem/mnt/supervisor`, which exists only because `_release`
  cross-compiles into `target/release/data` and the host mounts that as `/asystem/mnt`. Locally
  `SERVICE_DATA_DIR` is `target/runtime-system`, nothing puts a Linux binary there, and the container
  dies on `exec /asystem/mnt/supervisor failed: No such file or directory` — so `fab exe` and `fab st`
  have never worked for this module, and no systest was reachable without fixing it. Supervisor is the
  only Go module in the repo built this way: `network` compiles in a `golang:${ASYSTEM_GO_VERSION}`
  builder stage and ships `/asystem/bin/network`, which is what supervisor now does too. Three
  consequences worth knowing — the release-time cross-compile still runs and is still **needed** — `install.sh`
  starts a container only for form factor edge or server, so a `client` host never runs one and the
  cross-compiled binary is its only deliverable, `rue`'s being darwin/arm64 for `atops`; the in-image
  binary supersedes only the mounted copy on edge and server hosts; `buildx --platform` picks the builder's architecture, so the
  in-image binary matches the target host by construction rather than by a separate `GOOS`/`GOARCH`
  pair; and `src/build/resources/checkalive.sh` had to follow the path, since it `pgrep`s the binary
  by its absolute path. `.env_test`/`.env_exec` also pin `SERVICE_LOCAL_RUNTIME=native`, or every
  local run compiles Go under QEMU. The builder stage re-downloads the module cache on every image
  build, which is a minute or so and is exactly what `network` already pays; a BuildKit cache mount
  would fix it for both and belongs in neither module alone.
- **The pulse's own tombstone branch went to QoS 1 with `MarkDelete`.** Step 3 named only the deletes
  listener, but `process` publishes the same two forms for the interleave case and would have been the
  one remaining departure at QoS 0 — the two paths were meant to stop differing, and leaving one at
  QoS 0 would have re-opened case 8 through the back door.
- **The systest found a metric that has never worked, and it is not one this plan was looking for.**
  `newHostProbe` builds a `cpuUsageSampler` and a `diskUsageSampler` and **no `networkUsageSampler`**,
  so `hostProbe.usedNetwork` took its nil guard on every poll and `host/used_network` has been
  `faulting [host] with [no network sample taken, the probe was created without a network sampler]` at
  **ERROR**, on every host, since it was written — a red box and a permanently absent InfluxDB column.
  Nothing caught it because the sampler is not injected in any test and the estate has no assertion
  that a metric ever reads. One line fixes it; the point worth keeping is that the module's **first**
  systest found it on its **first** run, which is the argument for step 7 that the plan's own case
  makes less well.
- **The fixture cannot drive `host/temperature`, so that row was dropped and inverted.** The plan's
  fixture table plants an hwmon tree and expects 45 °C. `probe_lib_sensors.go` reads **bare `/sys`**
  by design — sysfs is kernel-global, so it is deliberately not rebased through `$SUPERVISOR_MOUNT` —
  and the planted tree is therefore unreachable from the container. The hwmon fixture is deleted, and
  the assertion becomes the more valuable half anyway: temperature carries `failed`, logs its absence
  at **WARN** under `errEnvironment` and never at ERROR, while the fan and the kernel log read
  **0 and ok** without `failed`. That is assertion 1 of the plan's four — no confident zero for an
  input that could not be read — asserted from the published payload rather than from the log, so it
  needs no DEBUG level and cannot drift with a message's wording.
- **Phase 1 step 11, the third row state, was not built, because its premise does not hold in the
  code.** The plan says a brand-new service "looks broken" since awaiting and failed both render as a
  blank cell and a failure paints the service name in `colourAlert`. Read against `drawValue`, the
  three states are already distinct: `runCacheMetricTask` returns **before** `Store` when the pulse is
  nil, so an awaiting record is never `Failed`; the sibling scan that alerts the service name tests
  `sibling.Value.Failed` and so never fires for an awaiting row; and `onDiscovery` stores the name
  record the moment the name arrives, so an awaiting service renders **its name in the ordinary colour
  beside empty cells**, where a failing one renders its name alert and an empty slot renders nothing
  at all. Building a fourth rendering against a symptom nobody has reproduced would churn the sixty-odd
  golden layouts for no observed defect. It stays in Phase 3 instead, tied to the one blank that **is**
  unexplained — the `mlflow` pulse — because if that turns out to be publish-side, this changes nothing,
  and if it does not, the state it needs to render is not the one described here.
- **The `/dev` bind target moved out of the data directory, or `fab clean` cannot clean.** The plan puts
  it at `/asystem/mnt/dev`, which is *inside* the `${SERVICE_DATA_DIR}` bind — so the container's own
  mountpoint materialises on the host as `target/runtime-system/dev`, and Docker Desktop leaves it
  carrying a `user:graham deny delete` ACL. `rm -rf` then fails with `Permission denied` followed by
  `Directory not empty`, which aborts `_clean` and therefore every `fab b`, `fab t` and `fab st` for the
  module until it is cleared by hand with `chmod -N`. `/asystem/dev` is outside every bind, so the
  mountpoint stays in the container's own filesystem and nothing is created on the host at all.
- **Every log line changed keeps its neighbours' rendered width.** `RunListeningStreamLoop` details
  are **32 characters wide** — 21 of its lines already were, and the number fields are padded (`%3d`,
  `%4d`) precisely so a column of them stays a column. New lines match it, one pre-existing outlier
  (`[%4d] topics [%3d]+[%2d] restored`, 33) was brought to 32, and the only details allowed to vary
  are those ending in a `%v` error or a `%s` topic, which cannot be padded. `RunAllProbesPublishLoop`
  has no single house width, so the five readback lines match their own anchor instead — the existing
  `[%s] host, rediscovered [%3d] topics` at 35 — and the no-op case reuses that sentence with a
  literal `[  0]` rather than inventing a second wording.

---

## Phases

Restructured around **what can be finished and proven on the dev machine** against what genuinely
needs the estate. The original numbering is kept in brackets, since the sections above refer to it.

The dividing line is not difficulty, it is **evidence**. Everything whose correctness is a property
of the code, the packaged image, a broker and a docker socket is Phase 1 and lands in one pass, each
step carrying the systest or Go assertion that proves it. Everything whose correctness is a property
of *the estate over time* — how often a departure is lost, whether the reconcile still earns its
place, why one ghost painted and its neighbour did not — is Phase 3, and cannot be brought forward by
building more. It can only be brought forward by **releasing Phase 1 and collecting**, which is why
Phase 3 is written as a collection protocol rather than as a change.

### Phase 1 — everything the dev machine can prove, now [was Phases 1, 2 and 4]

Eleven steps, landing together. Each names the assertion that holds it, and **no step lands without
one** — a change to a lifecycle this delicate that nothing exercises is indistinguishable from a
regression waiting for a release.

| # | Step | Was | Proven by |
|---|---|---|---|
| 1 | **done** — delete the shutdown tombstone-all | 1.1 | systest: `docker stop`, then the host's retained data topics still exist. Go: cancel the publish loop, same assertion |
| 2 | **done** — every silent return in the drop inventory instrumented, readback first | 1.2 | Go: a malformed retained name is `rejected` at ERROR naming `unmarshal`, read out of a `scribe` buffer, rather than returning silently. The **diagnosis** it enables is Phase 3 |
| 3 | **done** — `MarkDelete` and the pulse branch both publish both forms at QoS 1 | 1.3 | Go: subscribe, trigger a delete, assert nil-pulse JSON then empty payload, retained topic ends cleared. Systest: same over the real image |
| 4 | **done** — `databaseConnect` off the startup path, behind an `atomic.Pointer` | 1.4 | Go, under `-race`: the database backs off for 3.5 s against a dead endpoint while the first publish still lands at 2.07 s, and the client is stored and read across goroutines with no race. The systest has a *reachable* influx, so it cannot cover this |
| 5 | **done** — first poll tick immediate | 1.5 | Go: the first retained publish lands at **2.05 s** against a budget of one poll period, and at **5.06 s** with the tick removed. Deliberately not a systest assertion — container boot dominates and would only blunt it |
| 6 | **done** — compose stanzas parameterised, env files added, image builds its own binary | 1.6 | It is what makes steps 7-9 runnable at all; the fixture tree below is the assertion |
| 7 | **done** — 15 cases, and it found the dead network sampler on its first run | 1.7 | Itself |
| 8 | **done** — fixture tree, minus the temperature row it cannot drive | 1.7 | systest: inert-versus-errored, and the levels, per the table in *How to test* |
| 9 | **done** — publish batch sorted by GUID | 2.1 | Go: `Take` returns a batch sorted by host, service then metric, which is what makes a pulse reproducible; asserting the rendered protocol instead would test `sort.Slice` in `render` rather than the map iteration that was actually non-deterministic |
| 10 | **done, inverted** — ghost derivations *stated*, never inert, see Deviations | 2.2 | Go: a configured service with no container states its derivation and logs no `unstated` ERROR |
| 11 | ~~The third row state — present but not yet reporting~~ **dropped, see Deviations** | 4 | — the three states already render distinctly, so there is nothing to build until the unexplained blank is diagnosed |
| 12 | **done** — the reconcile retry's lost update fixed | new | Go, under `-race`: the retry branch re-reads `reconciles[host]` under the lock and re-arms only when the entry is still the one it collected, logging `deferred [superseded] by a newer schedule` at DEBUG otherwise. See *The reconcile's own defect* below |
| 13 | **done** — the barrier in **shadow mode**, behaviour unchanged | new (C, demoted) | Go: `compareBarrier` is table-tested over all five outcomes out of a `scribe` buffer, and the test was run with the comparison forced to `true`, where two cases fail. The stream loop emits `returned`/`shadowed` against a real broker, clean under `-race` |

**Landed, and each assertion was checked against the old behaviour before being trusted.** A test that
passes for the wrong reason is worse than none, so every regression assertion was run once with its fix
reverted: the graceful stop reported `used_memory cleared after a graceful stop`; the departure
reported `pulse ok[OK] value[zztest] in the form before the empty payload`; the first publish moved
from **5.06 s** to **2.05 s**, against a budget that is the poll period itself, so the test
discriminates on the ticker rather than on a margin; and the ghost reported `derivation: got empty want
stated`. The unreachable-database case backs off for 3.5 s on its own goroutine while the first publish
still lands at 2.07 s, and the whole engine suite is clean under `-race`, which is the `atomic.Pointer`'s
only proof. The systest is **15 cases in 139 s**, one of which has to wait out `mountSettle`'s two minutes to
see a share go red — which is why it sits after the read-only cases and before the mutating ones rather
than in a slow suite of its own. The departure lands in **8.9 s** end to end including the test's own
subscribe and settle, and the full stop-plant-restart-rediscover-tombstone cycle in **68.5 s**, of
which the container's boot is nearly all — that case is a correctness assertion, not a latency one,
and the latency number to trust is the Go test's.

**Shadow mode is built, and it is deliberately more than a latency probe.** The first sketch of step 13
only logged when the barrier returned. That is the *sizing* half and it answers nothing about
correctness, so what landed computes the reap set the barrier **would** produce and logs it beside the
one the timer actually used. The timer still decides; nothing reaps differently.

The mechanism is four small pieces in `engine.go`. `openBarrier` publishes a per-host nonce to
`supervisor/watch/<pid>/barrier` immediately **after** each resubscribe — the four sites being
`proveOnline`, the restart transition, the connect transition and the deferred retry — so the retained
flood is queued ahead of it. `barrierSeen` marks a service the moment `onData` or `onDiscovery` stores
anything for it. `onBarrier` fires when the nonce comes back, records the latency and computes
`cache.Services(host)` minus the seen set. `compareBarrier` then runs at reap time and reports one of
five outcomes:

**All seven lines carry the verb `shadowed`**, so `grep shadowed` is the whole instrument, and every
detail renders at the loop's 32 characters (the last two by the standard rule — the unbounded service
list moved last behind a prefix padded to 32). These are the rendered forms, taken from the tests
rather than transcribed:

| Line | Level | Meaning |
|---|---|---|
| `shadowed [  0] would reap, in [ 112] msec` | DEBUG | the barrier came back; the count is the shadow reap set and the latency is the sizing number against `reconcileDelay` |
| `shadowed [agreed] sets [  1] in [   0] ms` | DEBUG | both halves chose the same set — the sample size that says C is safe to promote |
| `shadowed [differ] barrier [ 1] timer [ 2]` | **WARN** | the finding, followed by the two lines below naming each set |
| `shadowed [barrier] reaps [zigbee2mqtt   ]` | **WARN** | the set the barrier would have reaped |
| `shadowed [timer] reaped, [svc-a,svc-b   ]` | **WARN** | the set the timer actually reaped |
| `shadowed [pending] barrier, cut [ 1] soon` | **WARN** | the flood was still in flight when the timer reaped, which is the "reaping too early" case |
| `shadowed [none] barrier on this reconcile` | DEBUG | a reconcile with no barrier, which should not happen once every site is covered |

**`pending` appears only as a bracketed state**, never as a bare word — an earlier draft of the
barrier-return line used bare `pending` for the shadow set's count, which collided with the
`[pending]` state and made a loose grep match both. It reads `would reap` instead, which also says
what the count *means* rather than how it was derived.

**Both changes are marked in the source, and `grep` is the removal list.** Everything shadow mode
added carries `TODO(shadow-barrier)` — 15 occurrences in `engine.go`, one on the test, one in
`scribe.go` — so `grep -rn "TODO(shadow-barrier)"` enumerates every symbol and call site to delete if C
is not adopted. The anchor comment on `hostBarrier` lists them explicitly. **These are deliberate
exceptions to the repo-wide no-comments rule**, the same standing exception `backupProbe.dormant()`
already holds: a temporary instrument that must be found and removed later cannot rely on someone
remembering it. If C *is* adopted, none of the shadow code survives as it stands either — the barrier
becomes the reap decision and the timed arm goes instead.

**Log purging is disabled for the collection window, and that is load-bearing.** `purgeLogFiles` deletes
every prior run's file on start, keeping only live pids. Supervisor is expected to be released several
times inside a month, and **each release restarts `serve` under a new pid**, so the purge would delete
the evidence on every release — the collection could never span more than the gap between two releases.
`logFilePurge` is therefore `false`, gated at the top of `purgeLogFiles` and logging
`retained [all] prior logs, purge disabled` at INFO so the state is visible rather than assumed. It is a
`var` rather than a `const` **only** so `TestScribe_PurgeLogFiles` can flip it and keep exercising the
purge logic — otherwise that code would rot untested for a month and re-enabling it would be a leap.
While it is off, `/var/log/supervisor` grows bounded only by lumberjack's own `MaxBackups` and
`MaxAge`, which is why those were sized first.

**Why shadow rather than adopting C outright.** The failure mode of a wrong reconcile is reaping a
*live* service, and it is silent, self-healing within a heartbeat and intermittent under load — and a
spurious reap logs **identically** to a correct one, since the watch has no ground truth. So "adopt it
and revert if it breaks" assumes a signal that does not exist. There is one weaker post-hoc tell in the
log (`reclaims … of <svc>` followed by a `register` for the same service, both INFO), but it lands after
the row has already blanked and can lag a heartbeat. Shadow mode reports the same condition **before**
anything is reaped, and is the only configuration that keeps a control arm.

**What it is expected to show, and the honest prior.** `mad` logged **zero** reconcile firings in
14.5 hours, because a stable server never reconnects. Every firing therefore comes from the wake path
on `rue`. So C's entire value is concentrated in one process on one machine, and the more likely
outcome of this collection is **delete the reconcile** rather than replace it — which is already the
first branch of Q1. Shadow mode is what tells the two apart at no risk.

**The two design points C depends on, both now settled.** The **fallback is skip-and-retry**, decided
and reasoned in *Barrier reconcile* above — hold the reap, re-open the barrier, resubscribe and
reschedule, only the retry reaps, and warn rather than guess after a bounded number of failures. It is
the whole-host guard's own shape applied to a second trigger, and it is what keeps C a deletion rather
than an addition. The **whole-host guard stays** (case 7), which is what converts an early-returning
barrier from a mass reap into a deferred one — and that matters because the ordering measurement was a
single-subscriber test broker, not six hosts under load. Note the two now share one mechanism, so C
adds no third recovery path.

**Neither decision should be acted on before the shadow data.** If `shadowed [pending]` is common the
barrier does not reliably return, and no choice of fallback rescues C.

**The reconcile's own defect, found while assessing whether it should survive C.** `due` was collected
under `reconcileMu`, the lock released, and the retry branch then **blind-wrote a stale local copy
back**: `reconciles[pending.host] = pending`. Two things could land in that window from other
goroutines. `onConnect` clears the map, so the write **resurrected a deleted entry** carrying a
pre-reconnect `started` cutoff. Worse, `scheduleReconcile` from `onStatus` or `proveOnline` sets
`retried = false` with a fresh cutoff, and the overwrite replaced it with `retried = true` and an older
one — **spending the whole-host guard on a reconcile that never used it**, so the next firing could reap
an entire host without the hold that exists precisely to stop that. The window is short, since
`ServicesBefore` is an in-memory walk, so this is rare rather than routine; the failure mode is exactly
the one the guard was written to prevent, which is what makes it worth fixing rather than tolerating.
The fix re-reads the entry under the lock and re-arms only when it is still the one collected. **It is
not throwaway work under C** — the plan's own deletion list keeps the whole-host guard and its retry
(case 7), so this code survives C either way.

**What was checked and found sound, so it is not re-litigated.** The reap cutoff is **single-clock**:
`onData` overwrites `value.Timestamp = time.Now().Unix()` before storing, so `ServicesBefore` compares a
locally-stamped receive time against a locally-stamped cutoff and no publisher-clock skew enters the
reap. (`proveOnline` deliberately does the opposite, comparing the *publisher's* stamp against the local
offline instant, which is what stops stale in-flight data reviving a host.) The wall/monotonic split
across `started`/`deadline` does what it claims. `Refresh()` is correctly conditional on something
actually having been reaped. The one residual is that the cutoff is second-granular — `seen < since` on
`Unix()` — giving the reap ±1 s of fuzz, harmless against a 10 s `reconcileDelay` but see below.

**Where a local assertion could not be built, stated so it is not claimed twice.** A case driving
`cache.Wake(brokerExpiry + 1s)` through `RunListeningStreamLoop` against a real broker was written and
**removed**: it passed identically whether or not the record was redelivered retained, so it
discriminated on nothing. Two reasons — the second-granular cutoff above makes a refresh and a cutoff
inside the same second indistinguishable, and the table driver's own publish refreshes the record
regardless. Ageing the record past a second boundary did not fix it. So whether a wake ever reaps a
**live** service is a Phase 3 estate observation (scenario 7), not something the dev machine proves,
and the same difficulty is why step 13 is not yet built. Do not re-add such a case without first running
it against the reverted behaviour.

**Steps 1, 2 and 3 are the minimum that changes behaviour**, and step 2 is the keystone: step 1 makes
the breadcrumbs survive, but if the readback is broken nothing reads them. Steps 4 and 5 are
separable and are worth landing even alone, since they make every metric on every host appear 3-6 s
sooner on every start. Steps 9, 10 and 11 touch nothing in the lifecycle and can land in any order.

**What the systest cannot cover, stated once so it is not claimed twice.** The binds and the
`rshared` propagation have to be stripped for the container to run on Docker Desktop, so those exact
stanzas stay untested — see the measured table in *How to test*. What is genuinely covered is the
packaged image, the capabilities and device rules, the generated `checkexecuting.sh`, the real
SIGTERM shutdown path, and every assertion above.

### Phase 2 — measure the barrier here, then decide C here [was Phase 0.2 and Phase 3]

**This is no longer a production measurement, and that is the one piece of the original Phase 0 that
moves forward.** `fab st` brings up the module's run dependencies, so the systest runs against a real
**VerneMQ**, not a stand-in — which is exactly the broker whose queueing behaviour the barrier
assumption rests on. So measure it here:

1. Publish a retained set at the sizes already measured in `CLAUDE.md` (443 and 546 topics).
2. Subscribe to the wildcard, publish a barrier nonce to a second topic, and record whether every
   retained message precedes it. Repeat enough times to catch an interleave, not once.
3. Record the result in this plan either way. It is a fact about VerneMQ 2.x, it will not change, and
   nobody should have to measure it twice.

**Measured, and it holds.** `test_retained_delivery_precedes_a_barrier_published_after_the_subscribe`
seeds **550** retained topics under a `zztest/barrier` namespace, then over **3** rounds subscribes to
the wildcard, publishes a non-retained nonce to a sibling topic from the connect handler, and records
the arrival order. Every round delivered all 550 retained messages **before** the nonce, with no
interleave. The namespace is its own, so nothing the module declares is touched, and the test clears
its retained set in a `finally` so a failure cannot strand it. Keeping it as a test rather than a
one-off measurement means a VerneMQ upgrade that breaks the assumption fails the build rather than
being discovered by a watch that reaps a live host.

**C is therefore viable and is still not being built — but the reason has been corrected.** This
section used to say *"building it now would remove the machinery whose firing rate is the evidence for
removing it"*. **That argument does not hold and should not be relied on again.** Under C the *reap*
survives; only the timing heuristic goes. A barrier reap fires when a service is in the cache and
absent from the seen set once the flood is provably complete — the same signal Q1 wants, minus the
timing noise. Today "fired" is ambiguous between a lost departure, a slow flood and a wake; under C
the middle one is eliminated by construction, so **C would make Q1's measurement cleaner rather than
impossible**. It does not make it unambiguous: a reap after a reconnect can still legitimately mean
"departed while we were disconnected" rather than "lost departure", and that is equally true today.

**The real blocker is that Phase 1's acceptance criterion is written in terms of the current
reconcile.** Phase 1's acceptance is *"the reconcile's `reclaims` line does not fire for that host"*,
and Phase 1 has never run on the estate. Landing C in the same release puts two substantial changes
into one lifecycle at once and leaves Phase 1 unvalidatable against its own test — if a watch blanks a
row there are two candidate causes and no way to separate them. That reason is **time-limited**: it
expires the moment Phase 1 has one release behind it, unlike the evidence argument it replaces, which
would have deferred C forever.

One smaller point argues the same way: the ordering measurement, while solid, is a single-subscriber
test broker, where production is six hosts under real load. (An earlier draft listed a second point —
that C's timeout fallback would keep the timed path alive, so C could not delete anything. That was true
of the *degrade-to-timer* fallback only, which has since been rejected in favour of skip-and-retry; see
*Barrier reconcile*.)

So C is buildable whenever it is wanted — with skip-and-retry as its fallback and its whole-host guard
intact (case 7) — and it would buy the deletion of `reconcileDelay`, `reconcileGrace`, the `connected`
cutoff, the `fromConnect` distinction and `RecordCache.ServicesBefore`. **D stays in reserve** for the
one case C does not cover cleanly, and no longer as a hedge against the ordering assumption failing.

**The augmented form is what should ship first, and it is Phase 1 step 12 below.** Publish the barrier
nonce and log when it returns, but leave the timed reconcile deciding the reap. No behaviour changes,
nothing to roll back, and it yields the one number nobody has: the real distribution of
flood-completion times measured against the 10 s `reconcileDelay` currently guessing at it. All three
outcomes are decisive — consistently inside the deadline means C is safe and `reconcileDelay` was
always over-generous; sometimes *after* it means the timed reconcile has been reaping before the flood
completed, which is a live defect invisible today and makes C urgent; never returning means the
ordering assumption fails under production load and D comes off the shelf. It also gives Q1 a sharper
partition than log archaeology: a reclaim firing **after** the barrier returned is a real lost
departure, one firing before it is a timing artifact.

### Phase 3 — production observation, later

**Nothing here is a code change.** It is the collection protocol for the three questions Phase 1
cannot answer on a dev machine, and it needs **two releases**: one to get the instrumentation onto
the hosts, one to validate against it. Supervisor is group 31 and deploys everywhere, so each is an
estate-wide release.

**The estate note below is resolved, so the confound is gone.** `max` and `may` each run exactly
their configured set now, and the one remaining configured-but-absent service is `openra` on `max`,
which carries a `.sleep` marker and is therefore deliberately dormant rather than a stray. Expect
**one** ghost estate-wide, on a known host, not the ghost storm this section used to warn about. Note
the sleeping-service and ghost paths are distinguishable in the log, so if a second ghost appears
during collection it is a real finding rather than noise to be read through.

#### What to simulate, and what to collect

Each scenario is staged deliberately — none of it waits for something to go wrong — and each names
the single line that decides it. Run a remote `watch` throughout with
`-L debug --log-subject=service/<name>`, and keep the serve-side log of the host being changed.

| # | Scenario | How to stage it | Collect | Decides |
|---|---|---|---|---|
| 1 | **Service removed** — *serve side now covered locally* | Stop a container and remove the module from that host's `config.json` schema | watch: `removals [<host>] removed; empty payload`, and the time from the serve-side `removals` line to it. The systest already proves the serve half against a real container, so what is left here is the **watch** half and the estate's latency | The departure path end to end. Target: gone from every watch inside one pulse |
| 2 | **Service added** — *serve side now covered locally* | Deploy a module to a host that did not run it | watch: `register [<host>] [n] topics added` and the row appearing. Again the systest covers the publish half; only the watch half needs the estate | Discovery is unaffected by the change to the departure path |
| 3 | **Service moved** | The above pair across two hosts, in one release | Both hosts' lines, plus that the row appears on exactly one watch grid at the end | The case the estate note describes, which is the one that produced the original symptom |
| 4 | **Graceful restart** | `install.sh start` on a host, or a plain release | serve at DEBUG: exactly one readback line per retained name, and step 2 made the four outcomes distinguishable — `rediscovered [%3d] topics` at INFO for a real registration, `rediscovered [  0] topics` for one that added nothing, `[unmarshal]`, `[nil] readback pulse`, `[empty] readback` for the rest, and **no line at all** for a name that was never delivered. watch: whether the row ever blanks | A, B and step 2 together, and this is the one collection that cannot be faked locally |
| 5 | **Ungraceful exit** — *now covered locally* | `docker kill supervisor` on one host, then start it | The systest asserts the will marks the host offline and the records survive; what the estate adds is the `rediscovered` line on the way back and that the crash path and the graceful path read identically | That there is **one** recovery path rather than two |
| 6 | **Broker recreate** — *restart covered locally, recreate not* | A vernemq release | watch: no `reclaims` line naming a whole host; serve: the reconnect republish. The systest restarts the broker and proves the daemon resumes publishing, but its store **survives** a restart, so the empty-store half is only reachable from a release | Case 7, the whole-host guard, against a genuinely empty retained store |
| 7 | **Watch suspends** — *the highest-frequency scenario, and the one that contaminates Q1* | Close the laptop for longer than `brokerExpiry`, then open it. Do it after a **short** sleep and a **multi-hour** one, since only the long one is certain to kill the socket | watch: the revive path taken (`liveness [false] frozen …` WARN, `[false] abandoned by paho` WARN, or `[false] closed, paho reconnecting` at DEBUG), then per host the `attached` line, the `transition by [connect]`, and the `reclaims` that follows — **including its service count**, which is the number Q1 needs partitioned | Case 9, the monotonic `hostReconcile.deadline`, and whether a wake ever reaps a **live** service. A non-zero `reclaims` here is a defect, not a lost departure |
| 8 | **A lost departure** | Not stageable — it is a dropped packet | The **absence** of scenario 1's watch line while the serve line is present | Whether QoS 1 closed case 8. Only a count over weeks answers this |

#### What this release changes that must be checked once, and only once

None of this is in the original plan — it is what implementing it turned up, and each item is a
first-release check rather than an ongoing observation. Do them on the release that carries Phase 1,
then never again.

- **The container now runs the binary from inside the image.** The `CMD` moved from
  `/asystem/mnt/supervisor` to `/asystem/bin/supervisor`, and the release-time cross-compile into
  `target/release/data` is still mounted but no longer used. If `buildx --platform` ever picked the
  wrong architecture the container would not start at all, so confirm on **each** host that supervisor
  is running and healthy after the release — this is the one change that can fail estate-wide, and it
  fails loudly rather than subtly.
- **The compose file is now interpolated rather than literal.** Every host-coupled bind is a
  `${SUPERVISOR_*_SOURCE}` variable whose `.env_all` value is the old literal, so the effect should be
  identical — but a missing variable would silently change a bind rather than error. Diff the mounts on
  one host against a pre-release capture: `docker inspect supervisor --format '{{json .Mounts}}'`, and
  confirm `/share` and `/backup` still carry `rshared` propagation, which is the one property the
  systest cannot cover because Docker Desktop refuses it.
- **`host/used_network` will report for the first time ever.** `newHostProbe` never built its sampler,
  so the metric has been erroring on every host since it was written; after this release it produces a
  real percentage against each interface's rated speed. Two consequences: a new InfluxDB column starts
  filling, and its `Bounded(Self, AtMost, 90)` pulse and `AtMost, 80` trend rules face real traffic for
  the first time — so if a host runs hot on its NIC, expect the first genuine amber from a rule nobody
  has ever seen fire. Check `jen` in particular, whose `eth0` is rated **100** Mbit where every other
  host is 1000, so the same absolute traffic reads tenfold higher there.
- **The `unstated` ERROR storm should stop.** A host with three ghosts logged 21 `unstated` ERRORs per
  pulse, 1638 in one uptime. After the release that count should be **zero**, and each ghost metric
  should instead carry a `computed [...] absent, service [x] is configured with no container` line at
  DEBUG. A non-zero `unstated` count afterwards means a metric somewhere else is publishing a value
  without stating a derivation, which is worth chasing on its own.
- **Expect a burst of counted drops per departure on the watch, and do not chase it.** A departing
  service tombstones **all 13** of its metric topics, each in two forms, so 26 messages are in flight.
  The **first** to arrive is enough: the watch removes the service on the nil-pulse form, and
  `RecordCache.Delete` removes every one of its records, so `watchDeletesListener.MarkDelete`
  unsubscribes all 13 topics at once. Everything still in flight then arrives for a topic no longer in
  the subscribed map and is counted in `dropCount`, surfacing as up to ~25 in one purge tick's
  `unlisted [n] drops` line. That is the design working. The number is a race — how much the broker had
  already queued before the unsubscribes landed — so it varies per departure and may be zero.

#### How to analyse the logs and decide

**This is the whole point of the collection, so it is written as commands rather than as advice.** Run
it against `mad` (the clean population — a server that never sleeps) and `rue` (the wake population — a
laptop that does) **separately**, and never pool them. Logs live in `/var/log/supervisor` on `mad` and
`~/Library/Logs/supervisor` on `rue`; archives are gzipped, so use `zgrep` or the `zcat` form below to
read a whole window at once.

```bash
LOGS=/var/log/supervisor                                   # rue: ~/Library/Logs/supervisor
cat() { zcat -f "$LOGS"/watch-*.log "$LOGS"/watch-*.log.gz 2>/dev/null; }
```

**Step 1 — how often does the reconcile fire at all?** This is Q1, and it is the question that decides
between delete, keep and replace.

```bash
cat | grep -c 'reclaims'                    # every firing, including the reaped-nothing ones
cat | grep 'reclaims' | grep -v '\[  0\]'   # firings that actually reaped, with the service names
```

| Reading | Verdict |
|---|---|
| zero `reclaims` on both watches | **delete the reconcile.** C is unnecessary rather than optional, and shadow mode goes with it |
| firings only on `rue`, all `[  0]` | the reconcile is exercised only by wakes and never reaps — still delete, but read step 2 first |
| firings that reaped, on either watch | a departure was lost. Go to step 3 to find out whether the reap was *correct* |

**Step 2 — was the timer ever wrong?** These two lines are the finding, and both are WARN, so they are
rare by construction and any hit is worth reading in full.

```bash
cat | grep 'shadowed \[differ\]'    # barrier and timer chose different sets
cat | grep 'shadowed \[pending\]'   # the timer reaped while the flood was still in flight
```

A `[differ]` is followed by two lines naming each set. **Both name fields are 14 wide, clipped with a
trailing `~`, padded with spaces when empty, and start at the same column (18)** — so the two sets sit
directly above one another and can be compared by eye, with an empty set reading as blank rather than
as absent. Read them with two things in mind. The **counts on the `[differ]` line are authoritative**,
not the names: `[postgres,sabn~]` against `timer [ 3]` is three services of which one is invisible.
And the **direction is what matters** — `barrier [ 0] timer [ 2]` means the timer reaped services the
barrier would have kept, which is the live-service reap this exercise exists to detect, while
`barrier [ 1] timer [ 0]` is the benign direction of a departure the timer merely missed.

Clipping is unambiguous across this estate: all 22 configured service names have distinct 7-character
prefixes, checked against the deployed `config.json`, and 14 characters holds `zigbee2mqtt` and
`homeassistant` whole. **The barrier latency is deliberately absent from this line** — it is already on
the `would reap` line for the same reconcile, which is what step 4 greps, so repeating it here bought
nothing and cost the name field six characters. **`[pending]` is the serious one**: it means the timed reconcile reaped before the
barrier proved the redelivery complete, which is the "reaping a live service" failure this whole
exercise exists to detect. **Any `[pending]` at all justifies building C.**

**Step 3 — corroborate a reap against a re-register.** A spurious reap and a correct one log
identically, so the tell is a service coming *back* shortly after being reaped:

```bash
cat | grep -E 'reclaims|register' | grep -A3 'reclaims .* evicted'
```

A `register` line for the same service within a pulse or two of the `reclaims` that removed it means the
service was never gone. This works without shadow mode and is the fallback if the barrier itself proves
unreliable.

**Step 4 — size the deadline.** Only meaningful once there are firings to size against:

```bash
cat | grep 'shadowed .* would reap' | sed -E 's/.*in \[ *([0-9]+)\] msec.*/\1/' | sort -n | tail -5
```

(`sed` rather than `awk` on a field index, because the padded `[ 112]` contains spaces and would split. Note the unit is `msec` on this line and plain `ms` on the `[agreed]` one — anchor on the whole token, not on `ms`, or the pattern matches both.)

The largest barrier latency against `reconcileDelay` (10 s) says whether the grace was ever close to
being too short. If the maximum is comfortably under a second — as the systest measured for 550 topics —
then `reconcileDelay` was always an order of magnitude over-generous, and that is an argument for
**deleting** it rather than for replacing it with a barrier.

**Step 5 — confirm the collection is sound before trusting any of the above.** Three ways this can
silently produce a clean-looking but empty result:

```bash
cat | grep -c 'purge disabled'      # expect one per process start; zero means logs were purged
ls -la "$LOGS"                      # expect archives spanning the whole window, not the last two days
cat | head -1                       # confirm the window actually starts when you think it does
```

The log file name carries the version that wrote it (`watch-10.200.1502-pid-2396749.log`), so a reading
can always be attributed to a release — which matters here precisely because several releases are
expected inside the window.

#### The three questions, and what answers each

- **Does the reconcile still earn its place?** [was Phase 2.5] Read the `reclaims` line across a
  month of releases and restarts. **No code change is needed to see it** — `engine.go:503` already
  logs a firing reclaim at **INFO** and only the reaped-nothing case at DEBUG (`:499`), so the line
  is visible at `watch`'s default level. **Never fires** → delete it, and C becomes unnecessary
  rather than optional. **Fires occasionally** → each firing is a lost departure; diagnose which
  case, and that decides between C and D. **Fires routinely** → Phase 1 did not work, and nothing
  should be built on top of it.

  **The count is contaminated by laptop sleep, and the verdict is wrong unless it is partitioned.**
  Every wake that ends in a reconnect runs the full `onConnect`, which **clears `hostStatus`**
  (`engine.go:415-417`) — so each host's retained `online` arrives with `known == false`, misses the
  heartbeat no-op branch, and takes `scheduleReconcile(host, fromConnect: true)`. A wake therefore
  schedules a connect-scoped reconcile on **every** host, every time. Confirmed locally by driving
  `cache.Wake(brokerExpiry + 1s)` against a real broker:

  ```
  liveness [false] abandoned by paho, reconnecting
  liveness [true]  session revived
  attached [   1] topics, [    2] wildcards
  observed [online] transition by [connect]
  reclaims [  0] services, after [     3] s
  ```

  So a laptop sleeping N times a day contributes N x hosts reconcile firings that are **not** lost
  departures. Counting them together is what would turn a healthy estate into a spurious "fires
  routinely".

  **The estate already runs both populations separately, so partition by *which watch*, not by log
  archaeology.** A watch runs continuously on **`mad`** (a server, which never sleeps) and another
  continuously on **`rue`** (the laptop, which does). `mad` is therefore the clean population — every
  reclaim it logs is a genuine steady-state firing — and `rue` is the wake population. That is a far
  more robust split than the `attached`-line heuristic this paragraph used to propose, which stays only
  as the fallback for a reclaim seen on `rue` alone.

  **First reading, already collected: `mad` has fired the reconcile zero times.** Its current log covers
  14.5 hours against a process up 1 day 17 hours, and `grep -c reclaims` returns **0** — not zero
  reaps, zero *firings*, since the reaped-nothing case logs at DEBUG and would appear. On a
  non-sleeping host with a stable broker the reconcile is not merely harmless, it is inert. That is the
  first real evidence for the "never fires → delete it" branch, and it was available before the Phase 1
  release rather than after it.

  **The binding constraint is log retention, not log content, and a month will not fit.** `watch` calls
  `EnableBufferAndFile(..., 10, 3, 7)` — lumberjack at 10 MB, 3 backups, 7 days — and `mad`'s file is
  **100 % DEBUG** (69 806 of 69 806 lines; zero INFO, WARN or ERROR), dominated by the per-tick
  `display render` and reconcile/census lines. It rotates roughly every **14.5 hours**, so three
  backups plus the current file is a window of about **2.4 days**. `MaxAge` never binds because
  `MaxBackups` binds first. A month-long sample is therefore impossible as configured, and the loss is
  silent.

  **Keep the reference watch at DEBUG — do not turn it down to `-L info` to save space.** That was
  proposed here and is wrong, and the reason is worth recording because the saving is tempting: only an
  *actual reap* logs at INFO (`engine.go:503`), while the **reaped-nothing** case is DEBUG (`:499`). At
  INFO the two readings Q1 must tell apart — *never scheduled* and *scheduled, reaped nothing* — are
  indistinguishable, and they are opposite verdicts. Never scheduled means delete it; scheduled but
  reaping nothing means it is doing work every reconnect and the barrier should be checking whether it
  ever reaps too early. The zero-firing reading recorded above was only available *because* `mad` runs
  at DEBUG.

  **So retention has to be solved on the retention axis, not the verbosity one.** Measured, the
  dimension filters barely help: `--log-source=engine` drops the display half and no more (33 222 of
  71 171 lines), taking the window from ~2.4 to ~4.5 days.

  **Done — lumberjack is now sized for a month**, as `logFileSizeMB`/`logFileBackups`/`logFileAgeDays`
  in `cmd.go` (10 MB, 60 backups, 40 days), shared by `watch` and `serve` so the two cannot drift.
  **`MaxAge` was the real binding constraint, not `MaxBackups`** — at 7 days it pruned before the backup
  count ever mattered, which is why raising the count alone would have silently achieved nothing.
  Measured inputs: `watch` at DEBUG writes ~16.5 MB/day (10 MB per 14.5 h rotation on `mad`), needing
  ~50 rotations for 30 days; `serve` at INFO writes ~2.2 MB/day (4.07 MB over 45 h in the container),
  needing ~7. Sixty covers both with margin. **The disk cost is near nothing because lumberjack
  compresses**: the observed archives are ~386 KB from a 10 MB file, about 26x, so a full watch window is
  roughly 20 MB and a full serve window about 1 MB. Note `serve`'s files live inside the container at
  `/var/log/supervisor` and are lost with it, so a host's serve history is bounded by the container's
  life however this is set — `docker logs` is the copy that survives a restart. Failing all that, harvest at least
  every two days (`grep 'reclaims' /var/log/supervisor/watch-pid-*.log >> …`), which is the same
  mechanism the laptop needs anyway, since **`purgeLogFiles` deletes every prior run's log on start** —
  a continuously-running watch is exempt only while its process stays alive.

  **A log file now names the version that wrote it** (`watch-10.200.1502-pid-2396749.log`), so a
  reading taken from an archive can be attributed to a release without guessing. That question was live
  the first time these logs were read: the `reclaims` count was only trustworthy after confirming the
  line existed in the deployed commit.

  **A quiet wake is not a wake that did nothing.** `SetCleanSession(true)` with `SetAutoReconnect(true)`
  means paho's own silent reconnect is still a *fresh* session — full resubscribe, full retained flood,
  reconciles scheduled — and it reports at DEBUG (`liveness [false] closed, paho reconnecting`) rather
  than at the WARN the frozen-past-keepalive path uses. That is why sockets appear to "resume on their
  own mostly" while the reconcile fires just the same, and it is the reason this partition cannot be
  done by counting only the WARN lines.

  **No local assertion covers the reap half, and one was attempted.** A case driving
  `cache.Wake(brokerExpiry + 1s)` through `RunListeningStreamLoop` against a real broker was written
  and **removed**: it passed identically whether or not the record was redelivered retained, so it
  discriminated on nothing. Two reasons it is hard here — `ServicesBefore` compares `Unix()` on both
  sides, so a refresh and a cutoff inside the same second are indistinguishable, and the driver's own
  publish refreshes the record anyway. Whether a wake ever reaps a **live** service is therefore a
  Phase 3 estate observation (scenario 7), not something the dev machine currently proves. Do not
  re-add such a case without first running it against the reverted behaviour.
- **Why did one ghost paint and its neighbour blank?** [was Phase 0.1] Restart `serve` on a host with
  at least two ghosts while a remote watch runs with `--log-subject=service/<name>`, and read it
  against that host's own `retained [n] bytes at qos [0]` lines for the same service. If the value
  topics were never published, the blank is publish-side and nothing in this plan touches it. If they
  were, a mechanism is unaccounted for and that becomes its own investigation — step 11 renders the
  state honestly either way, so it masks the symptom rather than fixing it.
- **What was the readback actually doing?** [was step 1.2's other half] Step 2 makes the four cases
  distinguishable — never delivered, failed to unmarshal, nil pulse, registered nothing new. One
  release with the instrumentation names which, and only then is a fix worth writing. It may already
  be fixed by step 1, since the graceful path was deleting the very topic the readback reads.

**Acceptance, on the release after Phase 1:** a departed service leaves every watch within one pulse;
a `rediscovered` line appears on the restarting host; and the reconcile's `reclaims` line does **not**
fire for that host. The third is the one that matters — it is the evidence the first question needs.

#### The one synthetic topic, for scenario 1 without a release

The estate cannot produce the orphan condition naturally — on `max`, config ∪ running covers every
retained service name — so create it deliberately:

```bash
mosquitto_pub -h "$VERNEMQ_SERVICE_PROD" -p "$VERNEMQ_API_PORT" -u supervisor -P "$VERNEMQ_TOKEN" \
  -r -t 'supervisor/macmini-max/data/service/zztest/name' \
  -m '{"timestamp":'"$(date +%s)"',"pulse":{"ok":true,"kind":4,"valueString":"zztest"},"trend":{"ok":true,"kind":4,"valueString":"zztest"}}'
```

Restart supervisor on that host and watch. **Before Phase 1** a `zztest` row appears on every watch
and survives until the reconcile reaps it at 10-16 s. **After** the new process rediscovers it, finds
it in neither docker nor config, and tombstones it within ~3 s. Clear it afterwards with `-r -n` on
the same topic. One topic, obviously named, fully reversible — and the phantom row it produces is
itself the demonstration.

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

## Estate note, resolved

**Resolved, verified 2026-09-07 — Phase 3 is no longer gated on it.** The `10.200.1502` release moved
modules between `max` and `may` and the containers had not followed: `max` was configured for
cloudflare, grafana, letsencrypt, openra, supervisor while running letsencrypt, mlflow, mlserver,
supervisor, and `may` was configured for influxdb3, mlflow, mlserver, sonarr, supervisor, tempstat
while running cloudflare, grafana, sonarr, supervisor, tempstat. Each host published a full record set
for ~3 ghosts that lived on the other, and `influxdb3` was installed on `may` but not running, which is
why `mad` dropped every database write.

The containers have since followed the configuration. `max` runs cloudflare, grafana, letsencrypt,
supervisor and `may` runs influxdb3, mlflow, mlserver, sonarr, supervisor, tempstat — each host's
running set is now its configured set, against a `config.json` still on `10.200.1502` and therefore
unchanged. `openra` is the sole configured-but-absent service, on `max`, and it carries
`/var/lib/asystem/install/openra/.sleep`, so it is deliberately dormant.

`influxdb3` runs on `may` and `mad`'s writes land — its per-pulse census reports bytes kept, and its
last `rejected` line is 09-05T16:55 against a container started 09-05T05:44, so roughly 39 hours clean
at the time of checking. None of this was caused by this work or fixed by it; it is why the symptoms
were visible, and the measurements Phase 3 asks for can now be taken without reading through it.
