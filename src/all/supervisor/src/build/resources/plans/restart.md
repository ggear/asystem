# Restart plugin

Supervisor restarts an opted-in service that has stayed unhealthy because something it depends on was not ready when
it started. It is not a general autoheal. It acts only when a restart can help, it is bounded, and it is never driven by
hand. Delete this file when everything below is done or dropped.

## Why

The 2026-11-19 shed and wake drill showed three services that came back unhealthy and stay so until restarted:

- `zigbee2mqtt` on `jen`: it reconnected to `vernemq` in the 5 s window where the listener accepted connections before
  its `vmq_acl` hooks were registered, was refused `Not authorized`, and `mqtt.js` does not retry that.
- `plex`: needs every `/share` mount present when it starts.
- `sonarr`: needs `/share/10`, which is on `mad`.

All three are fixed by one restart once the dependency is up, and made worse by a restart before it is. That asymmetry
is the whole design: **a restart is a way to pick up a dependency that is now available, so it waits for the
dependency**.

## Non-goals

- No command line to plan, inspect or reset. The plugin is transparent through its module logs and supervisor metrics
  and is never operated by hand.
- No module names in Go. A module teaches the engine through its `restart.sh` snippet, as with `backup.sh`.
- Not a replacement for a service fixing its own retry. The `vernemq` listener ordering stays a separate fix.
- Not for services that are stopped, and never for supervisor itself.

## Status

Built 2026-11-19 and tested, nothing released or deployed, and every host defaults to `SUPERVISOR_RESTART_MODE=observe`.

- `install.sh restart` (exit 0 restarted, 10 skipped, 1 failed) with `restart_service` shared with `schema`, whose
  output is unchanged; proven on a stub docker, and each rule fails its test when removed.
- The `restart.sh` contract, generator and prelude (`write_container_restart()`), proven by sourcing, by enrolment
  only through the module's own switch, and by byte-identical regeneration.
- In supervisor: the policy parser, the pure decision machine, the prerequisite checker, the ledger (write-ahead,
  refund, boot reset), the host sleep hold, the module log, the engine, and one metric beside `RST`. Every decision
  rule and every gate fails its test when deleted.
- The `/run` mount (`SUPERVISOR_RUN_SOURCE`) and the `awoke` line in `awake`.
- Enrolled, in observe mode: `zigbee2mqtt`, `sonarr`, `plex`.
- Closed on 2026-11-19 on the live hosts, see scenario 29 and the `plex` findings below.
- Not done, because it needs time on a real host: the observe week, and switching any host to `act`.

## Design

### Enrolment

Same shape as backup, three layers and one direction of knowledge.

| Layer | Owns | Lives in |
|---|---|---|
| Snippet (bash) | Opt-in, what must be true before a restart helps | `src/<host>/<module>/src/build/resources/restart.sh` |
| Generator (python) | Contract text, the `RESTART_*` prelude | `asystem/container.py`, `write_container_restart()`, called from `generate.py` |
| Engine (Go) | Watching, state machine, back-off, budgets, ledger, metrics | `probe_util_restart*.go`, `probe_impl_restart.go`, alias-only `engine_impl_restart.go` |

- No `restart.sh` in the installed module, no restarts. A module opts in with that file and one `.env_all` switch,
  `<MODULE>_RESTART=on`, which the prelude exposes as `RESTART_ENABLED`. Defaults live in Go, so no other variable is
  needed.
- Hooks are optional, detected with `declare -F`, each run in its own bash, as backup does. They are `restart_policy`
  (prints `key=value`, read once per installed version and cached) and `restart_ready` (exit 0 when the prerequisite
  holds now, only for what the declarative kinds cannot say).
- Prerequisites are declarative where they can be: `requires=mount:<path>`, `requires=mounts:all-cifs`,
  `requires=tcp:<host:port>`, `requires=mqtt:<host:port>` (a publish and subscribe round trip, using the image's
  `mosquitto-clients`) and `requires=healthy:<service>`. Go implements those five kinds once.
- Every prerequisite must hold **continuously** for `requires_stable` (default 60 s) before it counts. A `tcp:` check
  alone passes in the window where the broker listens but has not loaded its auth hooks, which is the exact fault this
  plugin exists for.

### The action

Supervisor restarts through the module's own installer, `install.sh restart`, run from
`/var/lib/asystem/install/<module>/latest/`. Nothing else restarts an enrolled container, so a schema restart and a
supervisor restart share one code path, wait on the same `checkexecuting.sh` and log the same way.

`restart` is added to `install.sh` the way `stop` and `sleep` are, and reuses what is already there. Nothing new is
written that an existing function already does.

| Piece | Reused as it is | Changed |
|---|---|---|
| Command parse | `COMMAND`, the `case` of accepted verbs, `SERVICE_COMMAND` export | `restart` joins the accepted list and the usage text |
| Container check | `present_container`, `docker ps` name test | none |
| Restart and wait | `restart_service`, `wait_service "checkexecuting.sh"`, `SERVICE_WAIT_RESTART_SECONDS`, `SERVICE_SETTLE_RESTART_SECONDS` | takes the reason as an argument and returns a status (below) |
| Bounds | `SERVICE_STOP_SECONDS`, `SERVICE_STOP_GRACE_SECONDS` | `docker restart` now runs under `timeout` with the same two, as `stop_service` does, so a wedged container cannot hold the caller |
| Output | `log_info`, `log_warn`, `log_error` | none |

**`restart_service` becomes one function with two callers.** Today it logs a fixed message about republishing retained
topics and always returns 0. It becomes `restart_service <reason>`:

- it logs `Restarting service to <reason> [<name>]`;
- it returns 0 when the container was restarted, 10 when it is not running (nothing to restart), and 1 when
  `docker restart` fails or times out;
- the wait on `checkexecuting.sh` stays non-fatal and does not change the return, since whether the service then turns
  healthy is the plugin's judgement, not the installer's.

`schema` calls `restart_service "republish its retained topics" || true`, so its behaviour and its log line are
unchanged apart from the reason now being a parameter, and a failure no longer hides a non-zero return from a future
caller.

**The `restart` branch sits beside `stop` and `sleep`, before the hooks:**

- it runs before `run_hook "./install_prep.sh"`, `.env` sourcing and the `rm -f "${SERVICE_SLEEP}"` that every other
  non-stop verb does. It needs none of them: `restart_service` uses `SERVICE_NAME`, the `SERVICE_WAIT_*` defaults and
  `image/checkexecuting.sh` relative to the install directory, and no hook may see `SERVICE_COMMAND=restart`;
- it refuses while the `SERVICE_SLEEP` marker exists (a module put to sleep on purpose), logging
  `Restart skipped, service is asleep [<name>]` and exiting 10, and it never clears that marker, which `stop` and
  `sleep` alone own;
- its exit status is the contract with the plugin: 0 restarted, 10 skipped (not running or asleep), 1 failed. Anything
  else is treated as failed.

The plugin runs it with its own `timeout` of `SERVICE_STOP_SECONDS + SERVICE_WAIT_RESTART_SECONDS + 30`, read from the
installed `install.sh` and not repeated in Go, and appends its stdout and stderr to the attempt's lines in
`restart.log`.

### What triggers a restart

All timings are read from the container's own `Healthcheck` in `docker inspect`, so none is a second copy of a number
the module already owns.

- Acts only on a container that is running and `unhealthy`. A stopped container (a shallow shed, a backup) is out of
  scope by construction.
- `settle = start_period + interval x retries`. A container whose `State.StartedAt` is younger than `settle` is not
  judged. It is `StartedAt`, not `Created`, because `docker start` after a wake resets the first and not the second.
  Docker cannot report `unhealthy` before `settle` has passed anyway, so this only guards a restart that has just been made.
- Eligible once it has reported `unhealthy` for one further `interval`, which filters a flapping check.
- Between attempts: after `k` attempts since the last stable health, `wait = min(1 h, max(settle, 60 s) x 2^(k-1))`,
  jittered by a deterministic 10%. The first attempt has no wait. A module whose service legitimately takes longer than `settle` to turn healthy
  sets `settle_min` in `restart_policy`.
- `n` resets only after `2 x interval` of continuous health, never on the first healthy sample.

### State machine

`ok -> suspect -> waiting -> restarting -> settling -> ok`, with `exhausted` reachable from `settling`.

| State | Meaning | Leaves when |
|---|---|---|
| `ok` | Healthy or not judged | unhealthy for one further interval |
| `suspect` | Unhealthy, inside the grace | grace passes, or health returns |
| `waiting` | Eligible, but a prerequisite, a budget or the back-off holds it | all hold-downs clear |
| `restarting` | `install.sh restart` in flight | it returns |
| `settling` | Restarted, inside `settle` | healthy for `2 x interval`, or `settle` passes unhealthy |
| `exhausted` | Budget spent | a new container id, a host reboot, or stable health |

The state words are declared once, as `metric.RestartState*`, and only Go writes them, so there is no second copy to keep in step.

### Flood controls

In order of importance:

1. **Prerequisite gate.** An unmet or not-yet-stable prerequisite means `waiting`, spending no attempt and no back-off.
2. **Attempt budget.** At most 3 restarts per rolling 24 h per service, then `exhausted`.
3. **Host budget.** One restart in flight on a host, at least 60 s between any two, and a per-hour cap per host. Several
   enrolled services unhealthy together are taken one at a time in a fixed order.
4. **Fail closed.** The attempt is written to the ledger **before** `install.sh restart` runs. If the ledger cannot be
   written, no restart is made. A restart that fails still counts.
5. **Observe first.** A global `RESTART_MODE=observe` does everything except run `install.sh restart`. It is the default
   for the first release.

### Host sleep hold

`asleep` and `awake` are run by `rackmains` over ssh, and a plugin restart that lands while a host is being shed would
start a container `asleep` has just stopped, which `asleep` then reports as a failed shed. So nothing is restarted on a
host that is asleep, being put to sleep or being woken.

- The signal is `/run/asleep.state` on the host. Supervisor does not see the host's `/run`, so its compose mounts
  `/run` read-only at `/host/run`. A directory is mounted, not the file, because docker creates a directory for a
  missing file mount.
- **Held while the file exists and its last line does not start with `awoke`.** `awake` appends `awoke <epoch> <status>`
  as its last act, in every outcome, and still keeps the file when it fails "to retry". Without that line, a failed
  `awake` (as on all four hosts after the drill) would block restarts for ever, exactly when they are needed. This is a
  change to `wake.sh`, one line, in the `system` module.
- On a reboot `/run` is empty, so the hold is gone.
- A deep shed also stops the docker daemon, and so supervisor itself, on that host, so the plugin is not running there at
  all. The hold is for the shallow shed on `max` and for the seconds before a deep one finishes stopping containers.

### Dependency appeared late

A service that started before its dependency (plex before a share, `sonarr` before `/share/10`, `zigbee2mqtt` before the
broker) cannot recover by itself, and Docker takes `settle` plus one interval, 9 minutes for every service enrolled
here, to say so. When the cause is known that wait is waste. After the first week in observe mode, S4 adds a fast path:

- eligible at once when the service is not `healthy`, has been up for at least its `start_period`, every prerequisite
  has held continuously for `requires_stable`, and **`StartedAt` is earlier than the moment the prerequisite became
  stable**, so the service demonstrably started without it;
- the budgets, the host hold and the sleep hold apply to it unchanged, and it never fires for a service that is
  `healthy`.

### State that survives

- The ledger keeps, per service: container id, total count, and the epoch seconds of recent attempts. It is
  `/home/asystem/supervisor/restart/ledger.json`, one writer, written atomically.
- A new container id (a release recreated it) resets that service. A change of host boot id resets the budget, because a
  reboot is a natural reset and a bad night must not leave nothing for the boot that follows.
- On supervisor start it does not act for one `interval`, since it knows nothing of how long a service has been
  unhealthy.

### Observability

There is nothing to run by hand. What is happening is visible in two places.

- **Module log.** Each decision and action is one line in `/home/asystem/<module>/restart/restart.log`, beside the
  module's other homes, newest 5 files of 1 MB. Lines follow the `[value]` convention, name the state transition and
  carry the reason a restart was held (`waiting [mount /share/10 not stable for 60 s]`). `install.sh restart`'s own
  output is appended under the attempt it belongs to. Supervisor's own log carries the same lines at the levels its
  logging rules give (a hold is DEBUG and a standing hold re-states itself periodically, a restart is INFO, an
  exhausted budget is WARN).
- **Metrics**, on the existing service scope, are two: `RST` (`restart_count`, now docker plus supervisor) and
  `RSTTRY` (`restart_attempts`, rolling 24 h, red at the third, which is `exhausted`). A state string and a next-time
  epoch were built and dropped (2026-11-19): a string metric cannot be red and the epoch is nobody's alert, so the
  state, the reason a restart is held and the time it will next be considered are in the logs only. `RSTTRY` needs an
  `entity_metadata.xlsx` row, which the user maintains, and the schema regenerated.

### RST

`RST` keeps its id, template and rules, and its source becomes docker's count plus the supervisor ledger for the
container. Its description now says so. Its trend rule (`AtMost 0`) turns red on any restart, which is the intent: a
service that needed healing is visible until its container is recreated.

## The first three

| Service | Host | Prerequisite |
|---|---|---|
| `zigbee2mqtt` | `jen` | `mqtt:` the broker, stable 60 s |
| `sonarr` | `may` | `mount:/share/10` |
| `plex` | `mad` | `mounts:all-cifs` |

## Slices

| Slice | Content | Done when |
|---|---|---|
| S0 | Ledger and `RST` wiring | done, `probe` and `scribe` packages pass |
| S1 | `install.sh restart` verb with `restart_service` refactored for two callers, `restart.sh` contract and generator, policy and hook reader | `schema` output unchanged, the three `restart` exits proven on a stub docker, a snippet generates byte-identically twice, contract test passes |
| S2 | Pure state machine and ledger with write-ahead, table tests | every transition and hold-down covered, each decision rule fails its test when deleted |
| S3 | Loop in `serve`, observe mode, host sleep hold (`/run` mount, `awoke` line in `awake`), module log, metrics | a week of observe on `jen`, `may`, `mad` that includes one shed and wake drill and one reboot of each, with every hold explained |
| S4 | Act mode, the dependency-late fast path, enrol `zigbee2mqtt`, then `sonarr`, then `plex` | each proven by a real broker or share outage on its own, and one drill showing a single restart each and none held wrongly |

## Pressure test

Each row is a scenario run against the design on paper, and what it changed.

| # | Scenario | What would go wrong | Outcome |
|---|---|---|---|
| 1 | Broker down, `zigbee2mqtt` unhealthy | A restart into a refusing broker burns attempts | Held by the prerequisite gate, no attempt spent |
| 2 | Broker listens but has not loaded auth hooks | `tcp:` passes, restart is refused again and counted | **Changed:** prerequisites must hold continuously for `requires_stable`, and `healthy:` is available |
| 3 | A share is down for good (`/share/41` today) and `plex` needs all of them | `plex` waits forever | Accepted: it stays `waiting`, visible in the metric and log, never a restart storm. Not softened to a partial restart |
| 4 | The ledger file cannot be written | Counts are lost and a service restarts forever | **Changed:** write-ahead and fail closed |
| 5 | Supervisor crashes between the ledger write and the restart | A restart is counted but never made | Accepted, conservative: one attempt is spent without effect |
| 6 | Supervisor released while a service is unhealthy | It restarts at once on stale knowledge | **Changed:** no action for one `interval` after supervisor starts |
| 7 | Host reboot, containers come up before their shares | Budget already spent the night before | **Changed:** boot id change resets the budget |
| 8 | A release recreates the container mid-wait | Counts carry over to a new container | New id resets that service; a release is not a restart |
| 9 | Backup stops and starts a module | Plugin restarts what backup stopped | Stopped containers are out of scope; a started one younger than `settle` is not judged. The shared module `flock` is also taken around the action (**to verify**) |
| 10 | Shallow shed stops containers on `max` | Plugin fights the shed | Same: a stopped container is never unhealthy |
| 11 | Everything unhealthy after a power cut | A thundering herd on the host | One in flight, 60 s apart, per-hour cap |
| 12 | A crash-looping service | Restarts forever | 3 per 24 h, then `exhausted`, which alerts |
| 13 | The health script is slow (`vernemq` is 2 m x 3) | Detection takes minutes | Accepted. The plugin never runs the health script itself, so it can only be as fast as the module's own check |
| 14 | `docker restart` succeeds but the service stays unhealthy | Looks like success | `settling` judges health, not the exit code, and an unhealthy result after `settle` counts toward the budget |
| 15 | `plex` is mid-stream when it is restarted | A viewer is dropped | Accepted: it was already unhealthy |
| 16 | Supervisor restarts itself | Loop | Never enrolled, checked by container name |
| 17 | Clock steps | A rolling window misreads | Windows use wall clock, waits inside a process use monotonic time |
| 18 | Two hosts' supervisors restart the same service | Double restart | Each acts only on containers of its own host |
| 19 | A module is asleep on purpose (`.sleep` marker) but its container is up and unhealthy | Plugin wakes what an operator put to sleep | **Changed:** `install.sh restart` refuses while the marker exists and exits 10 |
| 20 | `docker restart` hangs on a wedged container | The plugin call never returns, the host budget is held forever | **Changed:** `docker restart` runs under the installer's own stop timeout and the plugin bounds the whole call |
| 21 | The `schema` verb is refactored with `restart_service` | `schema` stops republishing | **Changed:** S1 requires `schema`'s output unchanged as an acceptance test, not just a green build |

Settled on 2026-11-19, on `max`, against the running supervisor container:

- **`install.sh` runs from inside supervisor's container, with no Dockerfile change.** The image is Debian with root, `bash`
  5.2, `coreutils` (`timeout`), `util-linux` (`flock`), `grep`, `awk` and the docker CLI, which is everything the
  `restart` branch calls (`docker ps`, `docker restart`, `docker exec` for `checkexecuting.sh`, `timeout`, `grep -Fxq`).
  `/var/lib/asystem/install` is mounted at the same path, so `SERVICE_INSTALL` resolves, and the branch is read-only on
  it. `bash -n` passes on the installed copy, and `install.sh bogus` ran in the container to its command parse and
  exited 1 with the usage error. Not needed by `restart` and so not a gap: `docker compose` (only `start_service` uses it)
  and the `.env` the branch never sources.
- **Watch item, shared with backup and not caused by this plan:** the image's docker CLI is `docker.io` 20.10.24 (API
  1.41) and the host engines are 28.5.1 (minimum API 1.24), so it works today. An engine that raises its minimum API
  above 1.41 breaks every `docker` call from supervisor at once, backup's included. The fix then is a newer pinned CLI
  in the Dockerfile and `docker_deps_base.txt`, not anything in this plugin.
- **`mosquitto-clients` is already in the image,** so a broker prerequisite can use `mosquitto_pub` and `mosquitto_sub`
  for a real publish and subscribe round trip, not only a TCP connect. That is the stronger check for the `vernemq`
  hook-load window and needs no new package.

Still to prove on a real host before S3: where the per-module `flock` lives, and whether supervisor can read the host
boot id (`/proc/sys/kernel/random/boot_id` is the container's own on some setups).

## Pressure test, rackmains shed and wake, reboots, slow services

Run against the timings read from the hosts on 2026-11-19. Every enrolled-type service there has `interval` 2 m,
`timeout` 30 s, `start_period` 1 m, `retries` 3, `start_interval` 10 s and `restart: always`, so `settle` is 420 s and a
service is eligible about 9 minutes after it starts. `plex` (`mad`) and `sonarr` (`may`) have been unhealthy since the
10:01 wake, 24 failed checks and counting, which is the case the plugin is for.

The wake order is `meg`, `mad`, `max`, `may`, serial, with `awake` waiting up to 60 s on `meg` and 30 s on the others.

| # | Scenario | What would go wrong | Outcome |
|---|---|---|---|
| 22 | `rackmains` sheds `may`, `mad`, `meg` deep | Supervisor on those hosts is stopped with the docker daemon, so nothing acts | Correct and wanted. Only `jen`, which is not shed, keeps a plugin running |
| 23 | Same shed, on `jen` | `zigbee2mqtt` goes unhealthy for the 10 minutes the broker is down and is restarted in the middle of it | Held by `requires=mqtt:`, state `waiting`, no attempt spent. It restarts once the broker has answered a round trip for 60 s |
| 24 | Shallow shed on `max` while a restart is in flight | `docker restart` lands after `asleep` stopped the container, which comes back up and `asleep` fails | **Changed:** the host sleep hold above, with the `awoke` line so a failed `awake` does not hold for ever |
| 25 | `awake` fails (status 4 or 6) and keeps `/run/asleep.state`, as on all four hosts today | A naive hold on the file blocks every restart indefinitely | **Changed:** only a file whose last line is not `awoke` holds |
| 26 | `awake` is half done when a service is eligible | A restart races `awake`'s own health wait | The file is held until `awake` writes `awoke`, and `awake`'s wait (60 s and 30 s) is shorter than any `settle` |
| 27 | `plex` on `mad` wakes before `may`'s shares exist | `plex` starts without them, sees empty mount points, stays unhealthy | Working as designed: `plex` waits on `mounts:all-cifs`, stable 60 s after `may` is up, then one restart. Without the fast path that is about 9 minutes after `mad` started, with it about 4 |
| 28 | `sonarr` on `may` | `/share/10` comes from `mad`, which wakes first | Usually healthy on its own. If not, the same single restart |
| 29 | Bind-mount propagation | A restart that does not pick up a share mounted after the container started | **Confirmed live.** `docker restart` re-resolves the bind sources, so `sonarr` came healthy in 45 s and `plex` saw all 11 shares |
| 30 | Planned reboot of one host | Containers (`restart: always`) and supervisor start together; the services look unhealthy while shares and the network settle | New boot id resets the budget, and supervisor takes no action for one interval after it starts, so nothing is judged in the first 2 minutes. `settle` covers the rest |
| 31 | Whole-site power cut, every host boots at once | Many services unhealthy together | Host budget serialises restarts, 60 s apart, one at a time. Each service still waits on its own prerequisite, so the order sorts itself out as `meg` returns first |
| 32 | `max` reboots (10:24 today) | `rackmains` crash-loops on a missing NUT socket, restarts do not help | Out of scope: `rackmains` is not enrolled. It would be a good later enrolment with `requires=mount:/run/nut/...`, since the cure is a host service, not a restart |
| 33 | A service takes longer than `settle` to turn healthy after a restart (a long library scan) | Judged failed, restarted again after a doubling wait, budget spent | Bounded: 3 attempts in 24 h, then `exhausted`, which alerts. Modules with a genuinely slow start set `settle_min` |
| 34 | A reboot or a power cut while `install.sh restart` is running | The attempt is lost | The attempt was written to the ledger first, so it counts. The restarted container is either up or restarted by docker's own policy |
| 35 | The plugin's own host loses the broker | Metrics and the `restart.log` are local, so nothing depends on the broker to act | Acts on local docker and local files only, apart from the `requires=` probes themselves |
| 36 | Supervisor on `jen` is released while `zigbee2mqtt` is unhealthy | Restart on stale knowledge | No action for one interval after supervisor starts, and the container is not judged until `settle` after its own `StartedAt` |

What this changed in the design: the host sleep hold, the `awoke` line in `awake`, `StartedAt` as the age, no wait before
the first attempt, `settle_min`, and the dependency-late fast path. What it did not settle, and S3's observe mode must
before S4 acts:

- ~~that a plugin restart really does clear the stale mount in `plex` and `sonarr` (scenario 29)~~ **Closed.** `sonarr`
  had been unhealthy 80 minutes: its `/library` was an empty directory docker created at 10:01, when `/share/10` was not
  yet mounted. `docker restart sonarr` made `/library/.sonarr` and `/downloads/.sonarr` visible and the service
  `healthy` within 45 s. `plex` showed the same fault in its own words: its container saw 8 of 11 share directories
  empty (the three local ext4 shares, mounted before it started, were fine) while the host saw them populated, because
  a container's bind of `/share` is `rprivate` and the cifs shares mounted after it started. After `docker restart
  plex` it saw all 11. Supervisor's own `/share` is `rshared`, so it sees the host's true state, which is what the
  prerequisite and `restart_ready` checks need.
- ~~that `plex`'s failing check is the mounts and not something else~~ **Closed, and it needed one more guard.** The
  check compares the number of `/share/*` directories with the number holding a `media` directory (11 against 3 when
  stale). After the restart that is 11 against 10, because `/share/31` is empty on every host: `may`'s 4 TB disk was
  deleted by `asleep` and has not come back. A restart cannot fix that, so `plex` would have spent its three attempts
  for nothing. `plex`'s `restart.sh` now defines `restart_ready` as that same comparison, run from supervisor's
  `rshared` view, so the plugin waits until every share has its `media` directory.
- that `jen`, which is not shed, is the only place the plugin runs during a shed, and what `jen` does during a shed that
  is longer than a minute.

## Review

Each slice ends with a review before it counts as done, in the order the global instructions give, because the early
passes change what the later ones see. Everything is judged against this module's `CLAUDE.md` and the neighbouring
`probe_util_*` files. The report is: defects found and fixed, then simplifications, then what was left alone and why,
then what was not checked, saying plainly when a pass found nothing.

1. **Correctness.** Read the logic, not the tests. Look hardest at state across a boundary: the ledger across a supervisor
   restart and a host reboot, hooks run in separate bash, `install.sh restart` run from another container, the order of
   the ledger write against the action, and what an interrupt leaves behind. A value set in one process is derived or
   handed over through a file the owner controls.
2. **Dead code.** Count references to every function, type, constant and flag. One used only by tests is deleted or moved
   into the test.
3. **Duplication.** One reader of the ledger and one of the policy document, shared by the engine, the `RST` probe and any
   test helper.
4. **Single-use helpers.** Inline a function with one call site unless it is a pure function with a real input space (the
   state machine and the back-off qualify and get table tests).
5. **Naming.** One `restart` prefix per domain, the same word in Go, bash and the metric template, verbs first for
   functions. Check for collisions, rename mechanically, build.
6. **Layout.** Exported and primary functions first, then helpers, types, constants; one test file per source file.
7. **Comments.** None, except a contract on the symbol that owns a boundary, whose spec block has a test parsing it
   against the declaration. Suppression directives stand bare.
8. **Tests.** Table-driven, `Test<FileCamel>_<Case>`, expected fields last, `expectedError` last. Assert states, counts and
   files, never log wording. **Prove each decision rule bites** by deleting the rule and watching its test fail, for the
   gate, the budgets, the back-off, the boot reset and fail-closed. Cover the failure path as well as success.
9. **Standards.** `gofmt`, `go vet`, the `go/ast` convention tests in `probe` and `scribe`, `shellcheck` on `install.sh`
   and every generated snippet, and the generator run twice with a byte-identical result. `install.sh` is packaged with
   `${VAR}` substitution into every module, so the change is read once in the substituted copy of a server module and
   of an edge one, and `schema` is run on a stub docker before and after to show the same lines.
10. **Prove it still works.** Run the changed packages first and the full suite once at the end. For the loop and
    `install.sh restart`, run the built image in an isolated container with a stub docker, then on a real host in observe
    mode. Read every diff that a build or regeneration writes.

Review is not permission to ship: no release, deploy or install runs as part of it, and `fab release` is read for what it
does to git and to remote hosts first.
