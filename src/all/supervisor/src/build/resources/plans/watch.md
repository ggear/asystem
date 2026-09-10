# Watch stream contract

How a `watch` learns which services a host runs, why a departed service lingered, and what was done
about it. **This work is complete** — every option is built, ruled out or deliberately shelved, and
the durable rules have moved into the module `CLAUDE.md`. What is left here is what a rules document
cannot hold: the root cause, the **negative results with their mechanisms**, the measurements behind
the constants, and two reusable procedures.

Status vocabulary: **built** is in the repo today, **ruled out** was tried and rejected on evidence,
**shelved** is designed and deliberately not built. Collapsed from 1653 lines on 2026-09-08; `git log
-p -- src/build/resources/plans/watch.md` has the phases, the options tables and the test plan that
were dropped once they were done.

---

## Root cause, built

**On a graceful stop, `serve` muted every watch and then sent tombstones the watch was guaranteed to
discard.** Both halves were deliberate on their own; together they were the bug.

The shutdown defer published the retained `offline` with a `WaitTimeout`, so it was acknowledged
*before* the tombstones that followed. `onData` drops an empty payload from an offline host — rightly,
because a shutdown tombstoned **every** topic and honouring them would delete every row on every
routine restart. So the tombstones accomplished nothing on the watch side, and their one lasting
effect was to **empty the broker's retained store**, destroying the breadcrumb the next process reads:
`may` logged **zero** `rediscovered` lines on restart. The graceful path deleted exactly what the
crash path depends on.

The 13 s `letsencrypt` row followed: nothing removed it, so the timed reconcile did, at
`reconcileDelay` rounded up to the next `purgeInterval`.

**Budget.** Pulse is 6 s, so the target is that a departed service leaves every watch inside one
pulse. The publish path was never the constraint — a tombstone goes out in the poll that detects it —
**startup was**: 7 s measured on `may` between the broker connect and the first sample, from a
blocking `databaseConnect` and a ticker that fired only after its first period. Both are fixed.

---

## Built

**A — the shutdown tombstone-all is gone.** Shutdown publishes the offline status and nothing else.
The honest regression: a decommissioned host leaves its retained data behind until the next vernemq
recreate collects it, which is already the behaviour for a removed module.

**B — `serve` reconciles its own retained set.** It re-subscribes to its retained
`supervisor/<host>/data/service/+/name` topics, registers what it finds, and its per-pulse services
reconciliation tombstones whatever docker no longer reports. **Measured doing more than it promised**:
that subscription is held for the life of the process, not just for the startup readback, so an orphan
name is registered the moment it is retained and tombstoned ~2 s later, with no restart involved.

**The timed reconcile stays**, and this was the last question to close. It fired 188 times across two
watches and five releases without reaping anything, which reads as dead code until you ask what it is
for. It is the only thing that clears **a module removed from a host across a release**:

1. `stop_service` publishes `offline`, so every watch mutes the host.
2. `install_pre.sh` sweeps every retained topic under the host's globs, breadcrumbs included.
3. The watch discards all of it — data empties because `onData` drops an empty from an offline host,
   name empties because **`onDiscovery` has no removal path at all**.
4. The new `serve` reads back an empty retained set and never learns the service existed.
5. Nothing refreshes the row and nothing tombstones it.

Staged deliberately (see *Staging an orphan*), both watches reported `reclaims [  1] removed` at 11 s
and 12 s. The lifecycle contract itself lives in `RunListeningStreamLoop`'s doc comment and in
`CLAUDE.md`; it is not repeated here.

---

## Ruled out, and why the idea will recur

**C — barrier-triggered reconcile.** After `resubscribeHost` forces a redelivery, publish a nonce to a
topic this watch also subscribes to; when it returns, the retained flood is complete, so anything not
seen since the resubscribe is gone. **The premise is false**, and it is the obvious idea, so read the
mechanism before proposing it again: the nonce proves the **broker** has finished delivering, while
what a restart reconcile waits for is the remote host **re-announcing** — which is in flight nowhere
when the nonce is published. On a release the retained store has just been swept, so the barrier laps
an *empty* flood, returns in 6-42 ms having seen nothing, and proposes to reap the whole host.

It was built in shadow mode — computing the set it *would* reap and logging it beside the set the timer
actually used, deciding nothing — and every disagreement it produced was that direction, naming live
services including `supervisor` itself. Two further faults it exposed in itself: on a wake the nonce is
a QoS 0 publish issued while the session is still settling, and **four of five barriers never returned
at all**; and it is *right* in the one case it was tested against by accident (a container restart,
where the store is intact and "not seen" genuinely means departed), which is exactly how a broken
instrument earns trust.

**E — lower `reconcileGrace` from 10 s to 3 s.** A **no-op**. `reconcileDelay` is
`max(2 x PulseMillis, reconcileGrace)`, so at the production 3 s poll x 2 the pulse term (12 s) always
wins; the estate's `after [ 11] secs` / `[ 12] secs` / `[ 13] secs` lines bracket the 12, not the 10.
Shortening the wait means changing the pulse multiple, and the staged reap says do not: those 12 s are
the window in which a restarted `serve` republishes.

**D — a roster topic, shelved rather than refuted.** The host publishes `host/services_roster` (str,
not persisted, `Always()`, no display box) and the watch registers names the cache lacks and
evict-and-deletes names the roster omits. Its benefit is real and singular: it would **state**
membership where the reconcile infers it from absence-of-refresh, clearing a removed module in one
publish (~3 s) rather than at the 12 s grace, with no cutoff and no whole-host guard.

Two claims made for it are false and were measured: it "collapses estate discovery from ~200 retained
topics to 6" — the real count is **26**, beside 438 retained `supervisor/#` topics in total — and the
name topics **cannot be dropped in any case**, because B's readback is built on them. So a roster is
**additive**, and both discovery paths would have to work simultaneously and indefinitely, since a
watch runs an old binary for weeks.

Its cost is a new source of truth: one bug in the ghost pass makes a whole host's membership wrong at
once, where today 26 independent topics fail independently. Against that, the condition it improves —
a module removed from a host followed by a release — happened **zero** times in the observation window
and last happened at the `max`/`may` migration. **Build it if module moves become routine** (a
migration project would flip this), or if a 12 s stale row becomes visible pain.

---

## Findings, 2026-09-08

Window 09-07T12:59 to 09-08T09:14, about 20 hours across releases `10.200.1531` to `1539` — five of
them, so restarts are over-represented rather than rare. Read per file and summed, populations
separate: `rue` is the laptop that sleeps, `mad` a server that does not.

| Population | Files / processes | Lines | `reclaims` | of those, reaped | `[agreed]` | `[differ]` | `[pending]` |
|---|---|---|---|---|---|---|---|
| `rue` | 2 / 2, sequential | 97 031 | 159 | **0** | 148 | 2 | 9 |
| `mad` | 5 / 4, overlapping | 127 275 | 29 | **0** | 25 | 4 | 0 |

Deduped to estate events — both watches see the same reconciles — that is **four `[differ]` events**
(jen 19:47:00, jen 20:30:14, mad 20:31:44, jen 20:38:04) and **two `[pending]` bursts** (16:56:05
across five hosts, 08:25:32 across four).

1. **Nothing has ever been reaped in steady state.** 188 firings, every one `[  0]`.
2. **Sleep is not the partition it looked like.** An earlier reading had `mad` at *zero* firings and
   concluded the reconcile was exercised only by wakes. `mad` never sleeps and fired 29 times, because
   a **release** restarts every `serve` and each restart is a transition.
3. **Every `[differ]` was the barrier over-reaping**, never once the direction shadow mode existed to
   catch, and the sets named live services.
4. **`[pending]` is a wake artefact**, all nine on `rue`, in two bursts covering every host at once,
   every one with `cut [ 0]` — the timer had reaped nothing, so no live service was ever harmed.
5. **Barrier latency**, for the record since sizing it was the point: n=150 on `rue`, min 13 ms,
   median 36 ms, max 135 ms — two orders of magnitude inside `reconcileDelay`. Findings 3 and 4 say the
   latency was never the binding question.

---

## Procedure — reading the watch logs

Logs are `/var/log/supervisor` on a host and `~/Library/Logs/supervisor` on the laptop. **This reads a
directory, which is several files, and that is where the readings go wrong.**

```bash
LOGS=/var/log/supervisor                                   # rue: ~/Library/Logs/supervisor
files() { ls -1 "$LOGS"/watch-*.log "$LOGS"/watch-*.log.gz 2>/dev/null; }
logs()  { files | while read -r f; do zcat -f "$f"; done; }
```

Three hazards, all silent:

- **A count over the directory is per watch *process*, not per estate event.** Two concurrent watches
  on one host both log the same reconcile. Dedupe by timestamp and host before quoting an event count.
- **Concatenation order is not a timeline.** `watch-*.log` then `*.log.gz` puts every archive after
  every live file, and `ls -tr` files an archive at its *rotation* time. Counts are unaffected;
  `head -1`, `grep -A3` and any context read are not — do those **one file at a time**.
- **A version and a pid are in every file name**, so per-file is also how a reading is attributed to a
  release. Take the census per file and sum it yourself.

```bash
logs | grep -c 'reclaims'                    # every firing, including the reaped-nothing ones
logs | grep 'reclaims' | grep -v '\[  0\]'   # firings that actually reaped
logs | grep 'removals' | grep 'purged'       # soundness: each line is a window a restart deleted
```

**Log retention was the binding constraint, not log content.** `watch` at DEBUG writes ~16.5 MB/day and
rotated every ~14.5 h against three backups and a 7-day `MaxAge` — a 2.4-day window, and `MaxAge` was
what bound first, so raising the backup count alone would have achieved nothing silently. It is now
10 MB / 60 backups / 40 days, shared by `watch` and `serve` so the two cannot drift; lumberjack
compresses ~26x, so a full watch window is ~20 MB. **Keep the reference watch at DEBUG** — only an
actual reap logs at INFO, so at INFO the two readings that matter (*never scheduled* versus *scheduled,
reaped nothing*) are indistinguishable, and they are opposite verdicts.

For a long collection, **harvest between releases** — that is the only route now, and it needs no code
change. The purge deletes every `*.log`/`*.log.gz` in the directory but keeps everything belonging to a
live pid, so a running `serve` or `watch` retains its own file and its own rotated archives; what a
release costs you is the previous process's window, because the restart runs under a new pid. There was
a `logFilePurge` var in `scribe.go` that short-circuited `purgeLogFiles` for exactly this, and it and
its test hook are **gone** — do not go looking for it. If a future collection needs one again, reinstate
it as a `var` rather than a `const` so the purge test can still flip it and the code cannot rot
untested, which is why it was shaped that way the first time.

---

## Procedure — staging an orphan

The estate cannot produce the orphan condition naturally, so create it. **Run from the module
directory on the dev machine**, the only place `.env` carries the broker host and port; root's home on
a host has none, and without it `mosquitto_pub` fails with `Invalid arguments provided`.

```bash
cd src/all/supervisor && set -a; . ./.env; set +a
mosquitto_pub -h "$VERNEMQ_SERVICE_PROD" -p "$VERNEMQ_API_PORT" ${VERNEMQ_TOKEN:+-u supervisor -P $VERNEMQ_TOKEN} \
  -r -t 'supervisor/macmini-max/data/service/zztest/name' \
  -m '{"timestamp":'"$(date +%s)"',"pulse":{"ok":true,"value":"zztest"},"trend":{"ok":true,"value":"zztest"}}'
```

**The payload shape is the correction.** This recipe used to send `{"ok":true,"kind":4,"valueString":…}`;
`ValueDataDetail` marshals as `{"ok":…,"value":…}` and carries neither field, so the scenario was
unrunnable as written and every attempt produced `rejected [empty] discovery has no service`. Diff
against a live topic before inventing a payload: `mosquitto_sub -t 'supervisor/+/data/service/+/name' -v -W 3`.

**Variant A, orphan with breadcrumb** — publish and watch. Result: `register … rediscovered [ 12]
topics` then `removals … [1] services [zztest]` **two seconds later**, honoured immediately by every
watch. No restart needed, and `reclaims` never fires. Retained state cleans itself up.

**Variant B, orphan the host cannot see** — the case that decides whether the reconcile earns its
place. A *running* `serve` eats the orphan, so it must be planted while `serve` is down:

```bash
ssh root@macmini-max 'docker stop supervisor'                       # watches mark the host offline
# publish the zztest name as above - proveOnline revives the host and registers the row
mosquitto_pub … -r -t 'supervisor/macmini-max/status' -m 'offline'  # re-assert the true, retained status
mosquitto_pub … -r -n -t 'supervisor/macmini-max/data/service/zztest/name'   # clear the breadcrumb
ssh root@macmini-max 'docker start supervisor'
```

That third command is the non-obvious one, and the reason is the mechanism worth keeping: **a service's
`name` topic is a bound metric as well as the discovery wildcard**, so an empty payload on it reaches
`onData`, which removes the service outright — *while the host is online*. Planting the orphan revives
the host through `proveOnline`, so without re-asserting the (already retained, and true) `offline` the
clear deletes the row instantly and the staging fails. Re-asserting it is a re-delivery of a true
value, not a fabricated one.

Observed end to end:

```
09:56:48  observed [offline] evicted [  6] services          host marked offline
09:57:12  (breadcrumb cleared - no removal line follows)     empty dropped, row survives
09:57:45  observed [online] transition by [restart]          back up, [ 75] topics resubscribed
09:57:58  reclaims [  1] removed, after [ 12000] ms          rue; mad the same at [ 11000] ms
```

---

## Not doing

- **Filling an empty row from the install tree.** A remote watch has no install tree, and it would be
  a second source of truth for the set this work exists to make singular.
- **Honouring empty-payload tombstones from an offline host.** The reason they are dropped is sound;
  the fix was A, plus the nil-pulse JSON form that already proves online.
- **Changing the `status` payload to carry membership.** Tempting — one topic, QoS 1, subscribed first
  at connect, already routed through `proveOnline` — but it is a bare `online`/`offline` string that
  health checks match with `grep -q "^online$"`, and the LWT payload is fixed at connect, so the will
  could never carry a live list.
- **A barrier or roster consumer in `RunListeningProbesLoop`.**

---

## Open

**Why did one ghost paint and its neighbour blank?** `mlflow` was blank for one pulse while `mlserver`
painted, both ghosts on `may`. Nothing in this document assumes a mechanism, and nothing built here
touches it. To diagnose: restart `serve` on a host with at least two ghosts while a remote watch runs
with `--log-subject=service/<name>`, and read it against that host's own `retained [n] bytes at qos [0]`
lines for the same service. If the value topics were never published the blank is publish-side; if they
were, a mechanism is unaccounted for.
