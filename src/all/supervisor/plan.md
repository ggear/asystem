# Plan — declared log dimensions and declared metric rules

Working document for three related changes to `supervisor`. It is deleted once its durable rules have landed in
`CLAUDE.md`, in the same way the schema-migration plan was.

The three changes are independent enough to ship separately. **The document orders them 1, 2, 3 for reading; the
execution order is 3 → 2 → 1.**

- **Phase 3 first**, because it is a rename and everything downstream depends on the final names: phase 1's `subject`
  column width is derived from the longest metric name, and doing the rename afterwards means re-deriving it.
- **Phase 2 second**, because it *deletes* four of the constants phase 3 would otherwise rename
  (`sensorWarnPulseOfMax`, `sensorWarnTrendOfMax`, `sensorFanPulseOfMax`, `sensorFanTrendOfMax`) along with
  `spinFanRespondingOK`. Renaming them first and deleting them second is wasted work, so phase 3 should leave those
  four alone and let phase 2 remove them.
- **Phase 1 last**, because it is the largest mechanical change and it wants the final metric names (for `SubjectMetric`
  and the width) and the final rule text (which phase 2 moves out of the derivation strings).

**Nothing here changes the record on the wire.** Phase 2 changes how `pulse.ok` and `trend.ok` are *computed*, not the
`{timestamp, pulse{ok,value}, trend{ok,value}}` envelope `metric.Payloads()` declares — so there is no broker payload
change, no Home Assistant change, no InfluxDB shape change beyond the two renamed columns in phase 3, and
`display_layout.go`'s `highlight` keeps working untouched.

## Why

Two problems, one root cause — things that are *stated in prose or in a closure* rather than *declared once and
projected*.

**The log's first three columns are not three dimensions.** Measured across 130 call sites:

- `tag` is 77 % constant — `state` on 100 of them, then `config` (15), `profiling` (14), `command` (1). A column that
  says the same thing four lines in five is a wasted column and a useless filter.
- `name` mixes three unrelated things — subsystems (`broker`, `database`, `display`, `config`, `install`), *directions*
  (`subscribe` 15, `publish` 7 — those are verbs, not names) and probes (`host`, `services`, `sensors`), plus `*`.
- `phase` has 48 values doing three jobs — lifecycle steps (`start`, `connect`, `reconcile`), subsystems (`docker`,
  `logs`, `mounts`) and metric families (`memory`, `processor`, `fan`, `drives`).

So there is nothing to filter on but level, and the subject of a line — the metric, service or host it is *about* —
is buried in free text.

**The ok predicates are closures, so the rule that decides green/amber/red is invisible.** A red `host/life_used_drives`
is currently ambiguous between 91 % wear and one new SMART error, and the second condition is not discoverable without
reading `probe_host.go`. Where the rule *is* stated in a log line today it was hand-typed into the derivation string
(`ok pulse at [<=90] pct trend at [<=80] pct`), transcribed from the closure and free to drift from it.

## Phase 1 — scribe dimensions

### The contract

Every record carries exactly three categorical fields plus severity, duration and free-text detail. Each categorical
field is a distinct Go type, so a call site cannot pass a string literal and the compiler enumerates the migration.

| Dim | Question | Type | Notes |
|---|---|---|---|
| `source` | which subsystem emitted it | `scribe.Source` — closed enum | 7 values, widest `database` |
| `subject` | what the line is *about* | `scribe.Subject` — constructed, never a bare string | metric, service, host, topic, path, or none |
| `action` | what happened to it | `scribe.Action` — closed enum | 15 values, widest `disconnect` |

`level` is orthogonal severity and the fourth filter — its contract is sharpened below, because it is not being applied
consistently today. `duration` and `detail` keep their meaning but lose their inline labels (see below): detail stays
last and unbounded.

`tag` dissolves: `profiling` becomes `action=census`, `config` becomes `source=config`, `command` becomes
`source=command`, and `state` was never information.

```
probe   host/used_memory        compute      0ms  computed [ 54] pct used, used [35601] MiB of total [65536] MiB
broker  macmini-meg             connect     12ms  observed [macmini-meg] status [online] trigger [restart] resubscribed [62] topics
probe   host/used_system_space  compute      0ms  failed with [no system filesystems measured of [6] classed system ...]
```

Filtering then reads as the sentence the dimensions form:
`--log-source=probe --log-action=compute,sample --log-subject=host/used_system_space`.

### The enums

```go
type Source uint8
const (
    SourceProcess Source = iota // serve, watch — process lifecycle, the subject names which
    SourceProbe                // host, services, sensors, install, mounts, logs, drives, *
    SourceBroker               // broker, subscribe, publish, command
    SourceDatabase             // database
    SourceDisplay              // display
    SourceConfig               // config
    SourceSchema               // schema
)

type Action uint8
const (
    ActionStart      Action = iota
    ActionStop
    ActionConnect
    ActionDisconnect
    ActionSubscribe
    ActionPublish
    ActionRegister
    ActionRemove
    ActionReconcile
    ActionDiscover
    ActionSample
    ActionCompute
    ActionRender
    ActionResolve
    ActionCensus
)
```

### Every existing phase, mapped

Nothing is dropped. 48 phases and 4 tags collapse into 14 actions. **This table was verified call site by call site
against each line's detail text, not its phase name** — five phases turned out to be doing more than one job, which is
the signal that the line was really two lines.

| Action | Phases absorbed |
|---|---|
| `start` | `start` `create` `init` |
| `stop` | `stop` `shutdown` `run`* `connect`* |
| `connect` | `connect` `reconnect` `revive` `wake` `probe`* `status`* |
| `disconnect` | `disconnect` `stall` `silence` `status`* |
| `subscribe` | `subscribe` `resync` `stream` `connect`* `status`* `command`* |
| `publish` | `publish` `write` `marshal` |
| `register` | `register` |
| `remove` | `tombstone` `purge` |
| `reconcile` | `reconcile` |
| `discover` | `discover` `scan` `docker` `install` `version` `memory`* `layout` `compile` |
| `sample` | `mounts` `drives` `logs` `sensors` `host` `service` `services` |
| `compute` | `metric` `memory`* `processor` `temperature` `fan` `allocated` `allocation` `inert` |
| `render` | `draw` `refresh` `resize` `rebuild` `render` |
| `resolve` | `resolve` `load` `parse` `hostname` `schema` |
| `census` | `census` `status`* |

The starred phases are the ones that split. Each was verified from its detail text, not assumed:

| Phase | Splits into | Told apart by |
|---|---|---|
| `run` | `stop` | `failed [%v] publish loop` reports a loop that **ended**; `create` already covers failing to start one, so this is not a `start`. |
| `connect` | `connect`, `subscribe`, `stop` | `broker [%s] … after [%d] attempts` is a connect; `attached [%d] topics and [%d] wildcards` is a **subscribe** reported under a connect phase; `failed [%v] listening stream loop` is a loop **ending**. |
| `status` | `connect`, `disconnect`, `census`, `subscribe` | `status [online] … resubscribed` is a host arriving; `status [offline], evicted [%d] services` is a host **leaving**; `heartbeat [no-op]` is a census; `payload [%s] unknown` is a **bad message arriving on a subscription**. |
| `probe` | `connect` | `alive [false] connection closed, paho is reconnecting` is `brokerRevive` testing the **session**, not sampling the world. Filing it under `sample` would put broker-session lines beside metric sampling. |
| `command` | `subscribe` | `observed [%s], service [%s], command [%s]` is a command **received**, not published. |
| `memory` | `discover`, `compute` | `missing [%s] compose not readable from [%s]` reads a declared limit; the host probe's `memory` computes a percentage of total. |

### Subject constructors

```go
func SubjectMetric(id metric.ID) Subject   // metric.GetIDName(id) — the only source of a metric's name
func SubjectService(name string) Subject
func SubjectHost(name string) Subject
func SubjectTopic(topic string) Subject
func SubjectPath(path string) Subject
var  SubjectNone Subject
```

Lines that are about no single thing — the `*` all-probes lines, the process lifecycle lines — carry `SubjectNone`,
which renders as `-` so the column never collapses.

`SubjectMetric` is backed by `metricBuildersByID`, so a log line cannot name a metric that does not exist or spell one
differently from the broker topic, the InfluxDB measure and the schema leaf — all four already derive from `template`.

### Levels, and what each one means

`level` is the fourth filter and the plan previously said only that it "stays as it is". It cannot: phase 1 rewrites
every call site, each one picks a level, and an audit of all 60 WARN/ERROR sites found roughly twenty that are wrong
under any consistent reading. The rule `CLAUDE.md` states today — ERROR is a violated contract or lost data, WARN is an
expected fault that heals itself — does not survive contact with the code, because half the WARNs are **permanent host
conditions that never heal** (no fans, no SMART support, composite sensor tier) and several ERRORs fire forever for
conditions nobody can fix.

The sharpened rule, fitted to what the code actually produces:

| Level | Means | Test |
|---|---|---|
| `ERROR` | a code defect, or a duty the service cannot perform | a developer changes code, or the service cannot run |
| `WARN` | the environment is not as required, and the service works around it | a person fixes a host, a mount, a capability, an install tree |
| `INFO` | the lifecycle timeline, **and** one-off facts about how this host is configured | nothing to fix; this is what the host is |
| `DEBUG` | anything that repeats without meaning | derivations, census, heartbeat no-ops, reconnect attempts, no-op reconciles |

The distinction that does the work is **INFO for a permanent, known host condition**. A Raspberry Pi with no fan, an
NVMe with no SMART support and a host whose sensor tier is `composite` are facts, not faults — they are stated once at
discovery and never change. Logging them at WARN trains people to ignore WARN.

**A probe must say whether a fault is ours or the environment's, because the emitter cannot tell.** `trackMetricFault`
sees only an `error`, so today it logs every sample failure at ERROR — including `no temperature read, discovery found
no … sensor under [/sys]`, which fires on every process start on a host that will never have one. The fix is a sentinel
wrapped by the sample function, exactly parallel to the existing `errProbeWarmingUp`:

```go
var errEnvironment = errors.New("environment cannot supply this reading")
```

A sample function wraps it when the cause is the host rather than the code (`no temperature read …`, `no services
configured for this host`, `kernel log unreadable`), and `trackMetricFault` logs `errors.Is(err, errEnvironment)` at
**WARN** and everything else at **ERROR**. ERROR then means "supervisor is broken", which is a filter worth having;
today it means "supervisor is broken, or this Pi has no fan".

**The reassignments**, by group:

| Sites | Now | Becomes | Why |
|---|---|---|---|
| `unrated`, `unreadable`, `unsupported` drives; `derived [composite]`; `skipped [%s] fan` | WARN | **INFO** | permanent hardware facts, stated once at discovery, nothing to fix |
| `exceeded [%d] MiB allocated`; `rejected` empty/non-unique container name; `missing [%d] containers with no install directory`; `memory` ×4; `version` ×3 | ERROR | **WARN** | estate and install-tree conditions the service works around — a person fixes the host, not the code |
| `kernel [%s] logged [%s]` | ERROR | **WARN** | reports that *the host* logged an error; supervisor is working. At ERROR it inflates supervisor's own error count with other people's faults |
| `held [%d] services … nothing reaped` | WARN | **DEBUG** | a no-op, by its own detail text |
| `observed [%s], status [online], revived by later data` | WARN | **INFO** | a host coming back is the lifecycle timeline |
| `marshal failed` | WARN | **ERROR** | our own data failing to marshal is a code defect |
| metric faults wrapping `errEnvironment` | ERROR | **WARN** | see above |
| everything else | — | unchanged | loop failures, unmarshal, unknown payload, refused subscribe, panics, missing probe registration and the `invalid`/`undeclared` family are all genuine code defects or prevented duties |

### Bare values with a header, not inline keys

The dimensions are **not** printed as `source=probe subject=… action=…`. Measured against a real line, the fixed prefix
before the prose is 85 columns today; with inline keys it would be 105, and with bare values in fixed columns it is 67
(see the width table below).
Inline keys would cost more than today's layout while adding a dimension, and the repetition is the same waste that
makes the 77 %-constant `tag` worth deleting. `detail=` goes with them — a fixed prefix width means the prose always
starts at the same column, so the label adds nothing.

```
TIME           LEVEL SOURCE   SUBJECT                  ACTION     DURATION DETAIL
08-25T09:36:42 DEBUG probe    host/used_memory         compute         0ms computed [ 54] pct used, used [35601] MiB of total [65536] MiB
08-25T09:36:42 DEBUG broker   macmini-meg              connect        12ms observed [macmini-meg] status [online] trigger [restart]
08-25T09:36:42 ERROR probe    host/used_system_space   compute         0ms faulting [no system filesystems measured of [6] ...]
08-25T09:36:42 INFO  probe    host/used_system_space   compute      1200ms restored [after [4] failed polls]
```

Keys survive where they are useful: **`--log-format=json` carries them**, and that is the machine-readable path.

Three rules make bare values safe, and all three are load-bearing:

1. **The three vocabularies must be disjoint**, asserted at `init()`. This is what lets a reader identify a bare
   `compute` as an action with no header in view. The proposed enums already satisfy it; without the assertion the
   scheme breaks silently the first time someone adds both a `SourceSchema` and an `ActionSchema`.
2. **An absent value prints `-`, never blank**, so `SubjectNone` still occupies its column and positional tools
   (`awk '$3=="probe"'`) stay stable.
3. **The header is written once, as the first line of the stream.** Not per rotated file: lumberjack exposes no
   rotation hook, so a per-file header would mean wrapping the writer to detect rotation — real machinery for a
   cosmetic gain. The cost is confined to the mode that needs it least. At INFO, `serve` emits a few lines a minute and
   will essentially never reach the 10 MB rotation size; at DEBUG, `watch` emits roughly 7 lines/s once derivations are
   on (~78 MB/day, ~8 rotations), but that is the interactive case where the live overlay is being read rather than a
   gunzipped backup. The format is fixed and documented, which is what makes a headerless rotated file readable.

   **The `watch` overlay is the exception.** Its buffer is a ring sized to the terminal height, so a header written as
   the first log line is evicted within seconds. The overlay must render its header as chrome — a pinned row above the
   scroll region — which is a display change, not a scribe one.

What this costs: a line pasted out of context loses its header, and `grep 'action=compute'` becomes `grep -w compute`,
which can hit detail prose. The intended replacement is the `--log-source/-subject/-action` filters, which filter before
writing rather than after. If that turns out to be missed, a `--log-keys` flag can re-insert the labels for a pasteable
line — off by default, and not worth building until it is wanted.

### The detail opens with a verb, and scribe owns its width

`detail` is free prose, but its **first token is a separate parameter**, not part of the format string:

```go
scribe.Log(SourceProbe, SubjectMetric(id), ActionCompute).Debug("computed", start, "[%3d] pct used, used [%d] MiB of total [%d] MiB", …)
```

scribe renders it in a fixed 8-wide column, so **the first `[` of every line falls in the same column** — 82, being the 73-column
prefix plus an 8-wide verb and its space. That is the property the current convention asks authors to maintain by hand,
and it is not holding: `probe_mounts.go` has `unreadable [%s]` (10) and `unsupported [%s]` (11), and `probe.go` has
`undeclared [%s]` (10), so today's lines do not line up. Making the verb a parameter moves the guarantee from author
discipline into the formatter.

The verb is not a fourth *dimension* — it is never filtered on, and it is deliberately not redundant with `action` or
`level`: the fault lifecycle uses `failed` / `failing` / `restored` on the same action at three different levels, and
that distinction exists nowhere else on the line.

**Enforcement is belt and braces.** `scribe` renders the token in a fixed 8-wide column — padding a short one,
**truncating** a long one — so the grid can never break at runtime whatever a call site does; and an **AST test**
asserts every literal is a lower-case word of **exactly** 8 characters, so neither padding nor truncation is ever
actually reached. A padded or truncated token in production would mean the test was bypassed, not that the design
allowed it.
The stricter alternative, a closed `Verb` enum like `Source` and `Action`, was rejected as a fourth vocabulary to
maintain for something that is never filtered.

**Every leading token is exactly 8 characters.** It need not be a verb — several are nouns and that is fine — but it is
always 8, so the first `[` is at a fixed column with no padding logic to reason about. A static sweep of all four call
forms (`Debug`/`Info`/`Warn`/`Error`, `derived`, `derive`) found **48 distinct tokens, of which 21 already are exactly
8**: `computed` (38 uses), `observed` (9), `rejected` (6), `database` (5), `received` (4), `resolved`, `reported`,
`defaults` (3 each), `unfilled`, `restored`, `register`, `measured`, `exceeded`, `declared` (2 each), `shutdown`,
`resynced`, `panicked`, `fallback`, `examined`, `detected`, `attached` (1 each).

The remaining 27 are renamed as part of the migration. Four are too long:

| Now | Length | Context | Rename to |
|---|---|---|---|
| `unsupported` | 11 | drive reports no SMART support, excluded from wear | `excluded` |
| `unreadable` | 10 | drive unreadable, excluded from wear | `excluded` |
| `unreadable` | 10 | mount table, kernel log | `noaccess` |
| `undeclared` | 10 | metric published a value with no derivation | `unstated` |
| `following` | 9 | now following `/dev/kmsg` | `followed` |

Twenty-three are too short:

| Now | Length | Context | Rename to |
|---|---|---|---|
| `invalid` | 7 | `[%d] remainder for [%d] hosts`; metric missing required fields | `unusable` |
| `missing` | 7 | version not readable from `[%s]` | `notfound` |
| `success` | 7 | `[false], removed from the poll set` | `prepared` |
| `dropped` | 7 | `[%d] topics of [%d], retrying on the next resync` | `rollback` |
| `version` | 7 | serve start banner — version, host, config | `identity` |
| `trigger` | 7 | `[%s], refreshed [%d] boxes` | `triggers` |
| `removed` | 7 | service removed by an empty payload | `removals` |
| `unrated` | 7 | drive model absent from the ratings | `unlisted` |
| `skipped` | 7 | fan declares no maximum speed | `bypassed` |
| `sensors` | 7 | `[composite] tier with [1] temperature and [1] fan inputs` | `topology` |
| `scanned` | 7 | `[6] mounts, system [5], shares local [1]` | `surveyed` |
| `resized` | 7 | `[120] cols, [40] rows` | `geometry` |
| `failing` | 7 | metric fault repeating, DEBUG | `faulting` |
| `derived` | 7 | composite tier, deriving from a drive sensor | `fallback` |
| `failed` | 6 (×15) | every failure line, including the first of a metric fault, ERROR | `faulting` |
| `broker` | 6 | `[tcp://…] connected after [4] attempts` | `endpoint` |
| `reaped` | 6 | `[n] services, host [%s], after [%d] ms` | `reclaims` |
| `format` | 6 | `[%v], rows [%d], cols [%d]` | `terminal` |
| `parsed` | 6 | `[4] services generation [1]` | `snapshot` |
| `kernel` | 6 | `[stamp] logged [message]` | `observed` |
| `alive` | 5 (×9) | `[false] client neither connected nor reconnecting` | `liveness` |
| `inert` | 5 | `[6] metrics are unimplemented` | `constant` |
| `held` | 4 | `[n] services, host [%s], nothing reaped` | `deferred` |

Four of these are **merges** rather than new words:

- both drive exclusions collapse into `excluded`, since both end in exclusion from wear and the detail says which;
- `kernel` folds into the existing `observed`, which already has 9 uses and is precisely what that line does;
- **`failed` and `failing` both become `faulting`** — the first occurrence of a metric fault and its repeat are already
  told apart by **level** (ERROR then DEBUG) and by the detail (`for [n] polls`), which is exactly what decision 5
  settled: a fault is a severity, not a separate vocabulary. `restored` stays distinct because it reports the fault
  *clearing*, which no level conveys.

`unrated` deliberately stays distinct as `unlisted` rather than merging into `excluded`, because its cause is different
— the model is absent from the ratings table rather than unreadable. Net vocabulary is **48 tokens down to 44, all
exactly 8**.

### Column widths — longest declarable value plus one space, derived at init

The current padder bakes widths in at `Handle` time and only ever grows them, so a line written an hour ago cannot align
with one written now. Widths are instead computed once in `init()` and are **exactly the longest declarable value**, with
**exactly one space** between columns and no padding beyond that — maximum compression subject to the grid holding. It
must be the longest *declarable* value, never the longest observed, or the widths vary at runtime again.

| Column | Width | Longest value |
|---|---|---|
| time | 14 | `08-25T09:36:42` — the same in every sink |
| level | 5 | `DEBUG`, `ERROR` |
| `source` | 8 | `database` |
| `subject` | 24 | `host/services_max_memory`, `host/failed_log_messages`, after phase 3 |
| `action` | 10 | `disconnect` |
| duration | 6 | `9999ms`, right-aligned, bounded by the `durationCoarser` ladder |
| `detail` | rest | unbounded, always last, no label |

That is **73 columns before the prose, in every sink**, against 85 on stdout and 96 in the file today — both shrink, the
file loses its separate shape, and one header serves all three.

**Time is one format everywhere, and it contains no space.** A space inside the timestamp would make it two `awk`
fields and shift every positional filter by one, which defeats one of the reasons for bare values. `08-25T09:36:42` is
sortable and unambiguous within a year; the year is recoverable from the file's mtime and from lumberjack's rotation
filenames, so five columns are not spent on a value that never changes mid-log. The shorter `09:36:42` was rejected
**because the header is written once per process**: a rotated file would then carry neither a header nor a date, leaving
a bare `03:14:07` with no legend. Choosing 8 would mean taking per-file headers back.

`source` and `action` are exhaustive over their enums. `SourceProcess` covers both `serve` and `watch`: a `serve`
process emits `probe`, `broker` and `database` lines too, so the binary's name is process identity rather than a
subsystem, and the subject names which one. `subject` is
`max(longest metric name in metricBuildersByID, 24)`; container names top out at 23 (`homeassistant_bootstrap`) and host
names at 11, so both fit under the metric-driven width. The header row is rendered from the same widths, so it cannot
drift from the body.

`init()` **asserts** rather than adapts: a value exceeding its column is a startup panic naming the offender, the same
posture as `verifyProbes()`.

**Nothing is clipped, and column widths are minimums rather than caps.** The file is the record of truth and must lose
nothing, so no value is ever shortened to fit. A value longer than its column pads to nothing and pushes the rest of the
line right, costing alignment on that one line and no information. Positional tools are unaffected, since fields stay
space-separated and a longer field is still field *n*. In practice it should never fire — container names top out at 23,
host names at 11, metric names at 24 after phase 3, and anything genuinely unbounded (a topic, a path) belongs in
`detail`, which is last and has no width at all.

**Truncation is a property of one sink only.** The `watch` overlay truncates each *line* at terminal width with a `~`,
which is what `display.go` already does; the file and stdout never truncate, at any width. This is the one place the
sinks legitimately differ, and it differs in rendering rather than in content — the same record reaches all three
whole.

**One record is always one line** — nothing wraps or folds onto a continuation, because every filter here is
line-oriented.

### Enforcement

- distinct types with unexported underlying types, so string literals do not compile;
- `init()` validates that every enum value has a `String()` and fits its column;
- extend `TestScribe_NoDirectLogging` (which already walks the AST for `slog.*` outside `scribe`) to require that every
  `scribe.Log(...)` argument is a constant identifier of the right enum type;
- one `Filter` object in `scribe`, consulted by every handler, so level and dimension filtering cannot diverge between
  the overlay, stdout and the file.

### CLI

`-L/--log-level` generalises instead of staying special-cased, one flag per dimension:

```
supervisor serve -L debug --log-subject=host/use          # host/used_memory, host/used_processor, host/used_system_space, …
supervisor serve -L debug --log-source=probe,broker
supervisor watch --log-action=compute,census --log-subject=host/,service/nginx
supervisor serve --log-format=json
```

**The grammar is: comma-separated prefixes, OR within a dimension, AND across dimensions.** A value matches if it starts
with any of the comma-separated prefixes, compared lower-cased. So `--log-subject=host/use` selects every `host/used_*`
metric, `--log-subject=host/` selects every host metric, and `--log-source=d` selects `database` and `display` — an
abbreviation affordance that falls out for free, and harmless here because a filter matches rather than selects, so
ambiguity costs nothing. An empty value means no filter rather than match-nothing.

**A prefix that matches no declared value is a startup error — but only for the closed dimensions.** `--log-action=xyz`
would otherwise produce a silent, empty log that looks exactly like a quiet system, which is the worst failure mode a
logging flag can have. `source` and `action` are exhaustive enums, so each comma value is checked to prefix at least one
of them and the process exits non-zero naming the offender and listing the valid values. `subject` is open — metric
names are known but service, host, topic and path subjects are not — so it cannot be validated, and a subject prefix
matching nothing is legitimately just a quiet log.

Filters are applied in the `Filter` object before a record is written, so a filtered line never reaches the file or the
overlay — `serve -L debug --log-subject=host/used_system_space` on a host is a targeted debugging session, not a
firehose to grep afterwards. `--log-format=json` carries the dimension names as keys and writes no header, since JSON
lines are self-describing. One object per line, keys `time` (RFC 3339 with the year, since JSON has no header to carry
it), `level`, `source`, `subject`, `action`, `verb`, `duration_ms` (an integer, not the rendered ladder) and `detail`.
The verb is its own key rather than the head of `detail`, matching how it is passed at the call site; `detail` keeps its
`[value]` bracket convention, which is redundant in JSON but keeps one format string serving both renderings.

Negation (`--log-subject=!service/`) is deliberately not part of the grammar. It is the obvious next request, and it
should stay out until something actually needs it — the moment prefixes gain operators they stop being prefixes.

## Phase 2 — rules as data in `metricBuildersByID`

### One field, one type, three leaf constructors

```go
type rule struct{ … }                                   // opaque, composable
type comparator uint8                                    // atMost, atLeast, above, exactly — all four kept

func always() rule
func bounded(id metric.ID, compare comparator, limit float64) rule   // whose value — Self, or another metric's, same window
func gated(gate gateID) rule                                         // named condition, bound by the probe
func all(rules ...rule) rule
func any(rules ...rule) rule
```

**All four comparators are kept, though the table uses three.** `atMost` and `exactly` carry every declared rule today
(`exactly(0)` on `failed_shares` and `failed_backups`, which is deliberately not collapsed into `atMost(0)` — it states
the intent more loudly) and `above` carries the fan. `atLeast` has no user and is retained for future rules. An enum
value with no user is an untested path, so the rule-evaluation and rule-rendering tests must exercise `atLeast`
explicitly rather than only covering what the table happens to declare.

**There is one bound constructor, and its first argument is always whose value is being read** — `Self` for the
metric's own, or another metric's ID. That is the only thing that varies; comparator, limit, window and rendering are
identical. Argument position 1 therefore means the same thing in every row, so the table has one shape rather than two,
one validator rather than two that must agree, and one grep (`bounded(Self` against `bounded(Metric`) that partitions it.
It is never cross-window — `pulseRule` reads the referenced metric's pulse value, `trendRule` its trend. It reads that
metric's **value**, not its ok flag: "ok if that metric is itself ok" would be a different constructor and is
deliberately not provided.

The alternative was two constructors — `bounded(atMost, 90)` for the common case and `siblingBounded(id, atMost, 80)`
for the rare one — which keeps the common case shorter, at the cost of a second name for a concept that is one concept,
and of hiding the parallel structure exactly where it matters most. The fan is the case that decides it: its two bounds
*are* the same kind of thing differing only in subject, and

```go
any(gated(GateFansAbsent), bounded(MetricHostWarnTemperature, atMost, 80), bounded(Self, above, 10))
```

says so, where two function names would not. The price is `Self,` on roughly 32 of 34 bound expressions, and a `Self`
sentinel that is a `metric.ID` which is not a metric.

Field names follow what the codebase already says everywhere (`PulseMax`/`TrendMax`, `pulseOKFunc`/`trendOKFunc`):
**`pulseRule` / `trendRule`**. Not `bounds`, which names only one of the kinds.

```go
MetricHostUsedProcessor:  { …, pulseRule: bounded(Self, atMost, 90), trendRule: bounded(Self, atMost, 70) },
MetricHostFailedShares:   { …, pulseRule: bounded(Self, exactly, 0), trendRule: bounded(Self, exactly, 0) },
MetricHost:               { …, pulseRule: always(),                  trendRule: always() },
MetricHostLifeUsedDrives: { …, pulseRule: all(bounded(Self, atMost, 90), gated(GateDrivesHealthy)),
                                trendRule: all(bounded(Self, atMost, 80), gated(GateDrivesHealthy)) },
MetricServiceUsedMemory:  { …, pulseRule: all(bounded(Self, atMost, 90), gated(GateServiceAggregate)),
                                trendRule: all(bounded(Self, atMost, 75), gated(GateServiceAggregate)) },
MetricHostWarnTemperature:{ …, pulseRule: bounded(Self, atMost, 80),  trendRule: bounded(Self, atMost, 60) },
MetricHostSpinFanSpeed:   { …, pulseRule: any(gated(GateFansAbsent), bounded(MetricHostWarnTemperature, atMost, 80), bounded(Self, above, 10)),
                                trendRule: any(gated(GateFansAbsent), bounded(MetricHostWarnTemperature, atMost, 60), bounded(Self, above,  5)) },
```

**There is no `bespoke` escape hatch.** Its only candidate was the fan, and the fan is fully expressible once
`bounded` takes a metric ID — which is a better outcome, because the per-window temperature thresholds become visible literals in
the table instead of arguments threaded through `spinFanRespondingOK`, and `GateFansAbsent` turns out to be the same
shape as the host-conditional inert cases (no fans, no kernel log, no shares), so "inert on this host" stops being
prose inside a sample function and becomes a printable term. The type is then total. Re-adding `bespoke` later is
additive and touches no call site, since `rule` is opaque; shipping it now with zero users would make it the path of
least resistance for the next author and it would arrive untested.

### What the task struct loses, and how a rule reads another metric

**`cacheMetricTask` loses `pulseOKFunc` and `trendOKFunc`.** That is the actual code change phase 2 makes and the plan
did not state it: today every task carries two closures built at the call site; afterwards it carries none, and
`runMetricCacheTask` looks the metric's `pulseRule`/`trendRule` up in `metricBuildersByID` and evaluates them. The task
keeps `valueKind`, `metricID`, `serviceName`, `sampleFunc`, `statsFunc`, `pulseFunc` and `trendFunc` — the parts that
say how to *sample and aggregate*, which stay per-probe — and loses the parts that say how to *judge*, which move to the
table. `newCacheMetricTask` drops two of its nine parameters.

**A `bounded` term naming another metric reads it from the record cache.** The mechanism was unstated and it matters:
the sibling's value is not reachable from `runMetricCacheTask`, which has no access to another probe's stats fields
(`warnTemperatureInt` is private to `hostProbe`). It is reachable from the cache — `RecordCache.LoadByID(id, host,
index)` returns the `Record` whose `ValueData.Pulse`/`.Trend` carry the value that task published **earlier in this same
pulse**. So the emitter reads the sibling exactly as the display does, through the published record, and needs no
probe-internal access at all.

That is also what makes the ordering requirement concrete rather than theoretical: the sibling's record must already
have been `Store`d this pulse, or `LoadByID` returns the previous pulse's value — silently, and off by one pulse. It is
the same read path either way, which is why nothing fails loudly. Hence `dependencies` ordering and its test.

### The binding contract

The table is a compile-time constant with no probe instance, so it **names** gates and the probe **supplies** them:

```go
probe.bind(GateDrivesHealthy,    func() bool { return !p.mounts().drivesErrored() })
probe.bind(GateServiceAggregate, func() bool { return aggregateStatus })
probe.bind(GateFansAbsent,       func() bool { return !loadSensors(p.sysRoot).hasFans() })
```

**A gate takes no window.** An earlier draft passed one so the fan's temperature term could pick its own threshold per
window; making that term a `bounded` on another metric moved the choice into the table, and the emitter supplies the
window to bounds. None of the three gates is window-dependent, so the concept disappears from the binding API entirely.
A gate named in the table with no binding, or
a binding for a gate nobody names, is a **startup failure** — the same posture as `verifyProbes()`. That check is the
entire reason to name gates rather than inline closures.

**Gate identifiers read as conditions that are true when healthy** — `GateDrivesHealthy`, not `GateDrivesErrored` — so a
printed `is [false]` always means "this is the thing that is wrong". A mix of positive and negative names makes every
fault line need a second reading.

**A gate is a named boolean over state, never a comparison against a threshold.** Every threshold must be a
`bounded` term so it lands in the table and prints. Guard it in the same AST test: flag any `bind(Gate…)` closure
whose body contains a comparison against a numeric literal.

### What the emitter prints

`runMetricCacheTask` evaluates the terms one at a time and reports each, so a fault names the term that failed:

```
compute  host/life_used_drives     ok [false], value [12] pct within [<=90] pct, gate [drives healthy] is [false]
compute  host/spin_fan_speed       ok [false], gate [fans absent] is [false], host/warn_temperature [82] pct not within [<=80] pct, value [0] pct not [>10] pct
compute  host/used_memory          ok [true],  value [54] pct within [<=95] pct
```

Units come from the `unit` field already in the table, so `pct` is never retyped at a call site.

### Other table changes for consistency

- **fold `metricInert` into the table.** It is currently a parallel map in `probe.go`; it becomes `inert: true` beside
  `pulseRule: always()`, so the startup line, the per-pulse derivation and the census count all read one row. It is a
  **bool, not the fixed value as a string** — the derivation line already prints the actual sample, so a stored value
  would never be read.
- **rename `skipDatabase` → `persisted`.** It maps 1:1 onto `schema.Measure.Persist` already; everything else in the row
  states what the metric *is* rather than issuing an instruction, and the negative reads badly beside the rules.

### Validation at init

- every metric declares a `pulseRule`; `trendRule` may be unset only where no trend is published;
- `bounded` on a `bool` or `string` metric is rejected — those take `gated`/`always` only;
- every `gateID` in the table is bound by exactly one probe at `Create`;
- every `bounded` target other than `Self` exists and is listed in the row's existing `dependencies` field (see
  decisions), and `Self` never appears there.

### What this deletes

The hand-typed `ok pulse at [<=90] pct trend at [<=80] pct` fragments come out of the derivation strings — the compute
line gains the rule *and* gets shorter — and `spinFanRespondingOK` disappears entirely, along with the last remaining
`derive` call in `probe_host.go`.

## Phase 3 — drop the `_of_max` suffix from two metric names

| Old | New |
|---|---|
| `host/warn_temperature_of_max` | `host/warn_temperature` |
| `host/spin_fan_speed_of_max` | `host/spin_fan_speed` |

`_of_max` is already implied by the unit (`%`) in both cases, and it is the *only* thing separating these two from every
other name in the table. Each name is projected into four places — the InfluxDB measure, the retained broker topic, the
schema leaf and (after phase 1) the log subject — so shortening them is worth more than the log columns that prompted
it. Together they take the longest metric name from **28 to 24** (`host/services_max_memory` and
`host/failed_log_messages`, tied), which is the `subject` width phase 1 adopts; doing the renames *after* phase 1 would
mean re-deriving that width.

Touched, in order, for each of the two:

1. `metric_build.go` — the `template`, and the ID constants `MetricHostWarnTemperatureOfMax` → `MetricHostWarnTemperature`
   and `MetricHostSpinFanSpeedOfMax` → `MetricHostSpinFanSpeed`;
2. `metric.go` — the ID constants in the enum block, keeping their positions (index must equal ID value);
3. `probe_host.go` — the task entries, `warnTemperature()` / `spinFanSpeed()`, and the constants `sensorWarnPulseOfMax`
   / `sensorWarnTrendOfMax` / `sensorFanPulseOfMax` / `sensorFanTrendOfMax`, which become plain bounds in the table
   under phase 2 and disappear as named constants;
4. `display_layout.go` — the boxes referencing the IDs (box label text is separate and unaffected);
5. `fab generate` — regenerates `schema/influxdb3/model/host.lp`, `describe.sh`, `verify.sh`, and the twelve per-host
   `schema/vernemq/model/supervisor/<host>/data/host/{warn_temperature,spin_fan_speed}_of_max` leaves;
6. the estate — see gaps for the stale retained topics and the stale InfluxDB columns.

Both renames must land in the same change: they share every step, and doing them separately doubles the estate cleanup
in gaps 1 and 2 for no benefit.

## Explicitly out of scope

**Projecting the bounds into the schema** — having `describe.sh`, the model leaves and the HA discovery JSON publish
"ok below 90 %" from the same declaration. It is a natural fourth projection and phase 2 makes it possible, but it
widens the blast radius to the generated artifacts and to Home Assistant, and it is not needed for either problem this
plan is solving.

## Done means

**Verification.** Nothing downstream parses the log format — checked: `system_test.py` does not read stdout or the log
file, and no `check*.sh` health script reads a log. So the format change is contained to this module and its own tests,
and no deploy-time surprise is waiting. Beyond `fab ut` and `fab st`, the change is confirmed by eye in the two places
it exists to serve: a `watch` session showing the aligned grid and the header, and one `serve -L debug --log-subject=…`
run on a host showing a single metric's whole story in one stream.

**Existing tests are rewritten, not just extended.** `TestScribe_FormatColumns` asserts offsets built from `widthTag`
and `widthEngine`, and `TestScribe_FormatDetailIsLast` asserts a `" detail=a [1] b"` suffix — both encode the layout
this plan replaces, so both are rewritten against the new geometry. `TestScribe_NoDirectLogging` survives and is
extended with the two new AST checks.

**`CLAUDE.md` sections superseded**, which is the exit criterion for deleting this document:

- **Log line layout** — replaced wholesale by the dimensions, the widths, the header, the verb column and the filters.
- **The level rules** inside it — replaced by the sharpened four-level contract, including INFO for permanent host
  conditions and the `errEnvironment` sentinel.
- **Metric diagnostics** — the derivation and census lines keep their meaning but change shape; the rule text moves from
  the derivation strings into the declared rules.
- **Adding a New Metric** — step 2 gains `pulseRule`/`trendRule` and, where it reads another metric, a `dependencies`
  entry.
- **Declared schema** — `skipDatabase` becomes `persisted`, and `metricBuildersByID` gains the rule fields.

## Decisions — all settled

1. **The renamed InfluxDB columns stay — decided: keep them, declare them retired.** InfluxDB 3 has no `DROP COLUMN` and keeps the column in the catalog
   whether or not data remains, so `warn_temperature_of_max`, `spin_fan_speed_of_max` and their two `_trend` twins
   persist in the `supervisor` measurement with their history. The measurement is **not** dropped and recreated.

   This is not a no-op, and that is the part to implement. `verify.sh`'s undeclared direction reads
   `information_schema.columns`, so the four would come back as fault rows on every run; `verify` exits non-zero on
   drift and `_run_local` passes no `warn=True`, so `fab schema` would abort at supervisor with the red `SCHEMA FAILED`
   banner and skip every module after it, permanently. The chosen mechanism is **declaration, not suppression**:
   `write_schema_database(database_retired=[...])` names the retired columns and the emitter counts them as declared
   but not written. **They appear nowhere else** — not in the model leaf, not in `describe.sh` — so the mechanism does
   one job, silencing a known-stale column, and adds nothing to the artifacts. A pattern-based ignore in `verify.sql` was rejected — it would stop
   verifying anything matching the pattern, including a genuinely undeclared column added later.

   **Scope note**: `retired` lives in the shared build library (`src/all/_/src/build/python/asystem/schema/`), so this
   is a change every module inherits, not a supervisor-local one. It is the same shape as the existing `persist=false`
   — a thing declared, and stated not to be written.

2. **Stale retained MQTT topics after the rename — decided: wait for the next vernemq recreate.** Twelve retained
   topics (six hosts, two metrics) become invisible to both `broker.sh`'s sweep and `verify.sh`, because the shipped
   globs match only the new names. The vernemq retained store is `tmpfs`, so any vernemq restart drops everything
   retained and only live publishers restore it — the ghosts collect themselves at the next vernemq release, at zero
   cost. A hand sweep (`mosquitto_pub -r -n` twelve times) and a one-release widened glob were both rejected as work
   disproportionate to twelve topics that expire on their own.

3. **Home Assistant entity rows — decided: there are none, confirmed against the spreadsheet.** `entity_metadata.xlsx` carries 31 supervisor rows, being
   per-service `health_status`, per-host `temperature` and their compensation sensors. Neither
   `warn_temperature_of_max` nor `spin_fan_speed_of_max` appears, so both renames are **code-only** and no spreadsheet
   edit is needed. Note `host/temperature` *is* an entity, and is not being renamed.

4. **External consumers of the old column names — decided: ignore.** The two old columns keep their history and stay
   queryable under their old names, so nothing is lost; anything outside the repo pointing at them (Grafana panels,
   ad-hoc queries) simply stops receiving new points. No repo grep gates the rename and no dual-write is built — the
   Grafana side is fixed by hand afterwards.

5. **`fault` — decided: severity only.** A failure is `level=ERROR` on whatever action was being attempted (`compute`,
   `connect`, `publish`), so `action` stays orthogonal to `level` and each dimension answers one question. There is no
   `ActionFault`; adding one would make `action` answer two questions and would lose what the code was doing when it
   failed.

6. **Gate binding lifetime — decided: bind at task construction.** `GateServiceAggregate` closes over a value computed
   per service per pulse, which is exactly where the services probe already builds its task table, so the binding is
   naturally per-service and per-pulse; `GateDrivesHealthy` and `GateFansAbsent` are stable and simply rebind to the
   same closure each time. No context object is invented to avoid a closure.

7. **Cross-metric evaluation order — decided: extend `dependencies` to carry it.** A `bounded` term naming another
   metric reads that metric's current window value, so its stats must already have been pushed this poll.

   **`dependencies` is not decorative — an earlier draft of this plan said so and was wrong.** `engine.go:39` reads it
   in `RunListeningProbesLoop` to seed a nil record for each dependency, which is what makes listening to
   `allocated_memory` also seed and probe `services_max_memory`. That existing meaning — *ensure this metric is
   probed* — **coincides** with what a rule dependency needs, since a rule reading another metric's value requires that
   metric to be probed. So this extends a field that already works rather than repurposing an unused one, and the
   seeding behaviour a rule dependency inherits is desirable rather than a side effect.

   Two consequences for validation: any non-`Self` `bounded` target **must** appear in `dependencies` (and `Self` never
   does), but the converse must **not** be required — `allocated_memory → services_max_memory` is a seeding dependency
   with no rule behind it, and demanding a rule for every entry would break it.

   **The hazard is silent staleness, not a crash.** In `probe_host.go` today `warn_temperature` is declared at line 194
   and `spin_fan_speed` at line 205, so the fan's ok-func reads this pulse's temperature and is correct by table
   position alone. Reordering the two would make it read the previous pulse's value — off by one pulse, no error, no
   test failure. That is exactly why the ordering moves into `dependencies` and gains a test, rather than staying a
   property of where a line happens to sit.

8. **Log overlay width — decided: leave it.** The estate's terminals are at least 114 columns and typically wider, and
   the change *improves* the overlay rather than straining it: the fixed prefix falls from 85 to 73, so detail gets 41
   columns at 114 where it gets 29 today. `display.go` truncates each overlay line with a `~` at terminal width and
   never wraps, so a narrow terminal degrades gracefully in any case. That line truncation is the overlay's alone — the
   file and stdout never truncate — and it is a rendering difference, not a content one.

   **Implementation note**: the overlay currently formats its own timestamp and level (`display.go`) while `scribe`
   formats the rest, so the two compose a line between them. Under a fixed geometry they must not each own part of the
   width — either `scribe` renders the whole line and the overlay draws it, or both read the same width constants.

9. **Migration shape — decided: one change.** Switching the `scribe` signature makes the compiler list every one of the
   ~130 call sites across `engine`, `display`, `probe`, `config` and `cmd`, as the derivation refactor did. Large diff,
   no site missed, no interim state. `scribe.Engine` and `scribe.Probe` are deleted rather than kept as shims — a shim
   would let call sites linger on the old shape indefinitely, which is how the present three columns drifted.

10. **Test strategy — decided: the full set.** `init()` assertions (every metric declares a `pulseRule`, every gate in
    the table is bound by exactly one probe, the three log vocabularies are disjoint, every enum value fits its
    column); table-driven tests for rule evaluation and for the rendered rule text, **including `atLeast`**, which the
    table does not use and which would otherwise ship untested; AST tests for gate purity (no numeric comparison inside
    a `bind(Gate…)` closure) and for `scribe.Log` receiving constant enum identifiers, extending the existing
    `TestScribe_NoDirectLogging`.

11. **`inert` typing — closed by simplification.** The field is a bool (`inert: true`), not the fixed value as a
    string, because the derivation line prints the actual sample and a stored value would never be read. No union type,
    no `valueKind` coupling.
