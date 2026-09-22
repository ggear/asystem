# Goimpl

Reimplementing `src/main/resources/image/backup.sh` (2295 lines of bash, 175 `BACKUP_*` variables, 112
functions) as a Go command, `supervisor backup`, alongside `watch` and `serve`. Status is marked per
section: **planned** is not in the repo, **built** is, **ruled out** was considered and rejected on
evidence. Everything below is **planned** unless marked otherwise. The design and rationale of what
`backup.sh` *does* is `backup.md`; this plan is only about moving it, and deliberately re-decides
nothing that document settled.

**Two declared exceptions, and only two.** The capture found two live defects in `backup.sh`; both
were fixed in the shell first (*What the capture found*), so the port reimplements the corrected
behaviour. Everything else is exact.

**Otherwise the whole point is that nothing observable changes.** The run tree, the four status documents, the
retained topics, the exit codes, the log columns, the CLI grammar and the env-var surface are all
contracts with something outside this file — Go's own probe, `backups.sh`, Home Assistant, the
operator's muscle memory, and 152 unit tests. A port that improves any of them has failed. Read
*The contract that cannot move* before anything else, and treat it as the acceptance criteria.

## Why — planned

Four costs, each measured against something already in the repo rather than asserted.

- **The shell is the only part of supervisor with no compiler behind it.** Every rule the module
  `CLAUDE.md` states about metrics, rules, schemas and topics is enforced at `init()` or by a
  `go/ast` test. The shell half is held to the Go half by six *string-equality* tests in
  `unit_test.py` — the state vocabulary, the four document shapes, the field readback, the scheduled
  hour, the CLI verbs. Those tests exist precisely because nothing else could catch the drift. Four
  of the six were written **after** a drift shipped.
- **The document writers are duplicated and the duplication is declared.** `backupDocument`'s doc
  comment says so in as many words: RUN has two writers with different fields and its payload declares
  the union. `backup_rollup`'s heredoc and `writeRunDocument`'s marshal are the same document written
  twice, and a test asserts the union rather than either.
- **Half the bugs `backup.md` records are bash bugs, not backup bugs.** `local uuid` unset under
  `set -u`; `backup_bounded` minting a phantom run directory; the host loop drained by `ssh` reading
  stdin; `${VAR:-default}` discarded by `varsubst`; `-` printed where a padded `-` was meant because a
  width moved out of a `printf`. None of those are possible in Go, and each cost a real incident.
- **Two languages for one concern.** `probe_impl_backup.go` already owns the schedule, the lock, the
  leader, the reaper, the cluster rollup and two of the four documents. The stage bodies are the only
  part outside, and they are reached by `exec.Command("bash", runner, ...)` with a CLI contract held
  by a test that parses the shell's dispatch `case`.

**What this does not buy, and must not claim to.** It is not faster, the work is `rsync`, `btrfs` and
`docker` either way. It does not reduce the external command surface: `rsync`, `btrfs`, `mount`,
`umount`, `findmnt`, `df`, `du`, `dd`, `dmesg`, `smartctl` and `docker` are still exec'd, just from
Go. And it does not remove shell from the estate — a module's own `backup.sh` stays shell forever
(*What stays shell*).

## The contract that cannot move — planned

Each row is a promise to a named consumer. Each gets a test in *Tests*.

| Contract | Consumer | Shape |
|---|---|---|
| run tree layout | `probe_impl_backup.go` `documents()`/`fingerprint()`, and the topic namespace | `<root>/<run>/status.json`, `<run>/stage/<stage>/{status.json,scrub.json,output.log}`, `<run>/stage/primary/service/<svc>/status.json` |
| the four documents | `metric.Payloads()`, the leader, three host metrics, `service/backup_status` | every field in `backupDocument`'s spec block, `omitempty` exactly as now |
| retained topics | Home Assistant, every watch, `verify.sh` | `metric.TopicBackup*`, QoS 1, retained, published on the same events |
| the six-word state vocabulary | `metric.BackupState*` | one Go constant set for both halves once the shell is gone |
| CLI grammar | operators, `install_post.sh`'s `abackup`, `backups.sh`'s dispatch | `start\|stop\|tail\|list\|auto\|help [run-id\|on\|off]` plus `--stage`, `--scrub`, `--quiet` |
| exit codes | `backups.sh`, the probe, operators | `0` ok, `2` usage, `3` already active or lock held, `4` run expired, `143` interrupted, and otherwise **the stage's own return** — `primary_start` returns the *count* of failed services, so a stage is not simply `1` |
| the flock | the probe's `cycle` and every hand run | `<root>/.lock`, one file, `LOCK_EX\|LOCK_NB`; `stop` deliberately never takes it |
| `output.log` is appended | a `stop` writing into a running stage's log | shell opens `>>`; Go's current `runStage` uses `os.Create` and truncates, so the two drivers already disagree — the port settles on append |
| log line columns | `abackup tail`, `abackups tail`'s `awk` banner filter | `[%-4s %-9s %8s] %s` — level, stage, `HH:MM:SS` |
| `abackup list` table | operators | `BACKUP_LIST_WIDTHS`, `BACKUP_LIST_RIGHTS`, the `+---+` rules, byte for byte |
| env-var surface | `probe_impl_backup.go`, `backups.sh`, operators, tests | every `BACKUP_*` normalised setting keeps its name, meaning and default |
| the module contract | 16 module `backup.sh` snippets | `bash <script>` with `BACKUP_SKIP_HOURS`, `BACKUP_SERVICE_RESTART`, `BACKUP_TIMEOUT_HOURS`, stdin `/dev/null`, fd 9 closed; `--prune-gfs <dir>` for the pruner |
| runs on the host, not only in the container | `abackup` on five hosts | the cross-compiled release binary already at `${SERVICE_INSTALL}/supervisor` |

**One new failure mode the port introduces, which needs a guard.** `abackup` exists only where
`install_post.sh` writes it, and it writes it only for form factor `edge` or `server`. The binary,
however, ships **everywhere** — the cross-compiled `supervisor` is the deliverable on a client host,
which is how `atops` runs on the laptop. So `supervisor backup start` becomes typeable on `rue`,
`jac` and `jem`, where it never was, and would try to mount and mirror a machine that has no business
running a stage. `executeBackup` must refuse when `config.HostStages(host)` is empty, with the same
exit 2 a bad verb gets, and a test must assert it. The `abackup` wrapper stays edge/server-only.

**The last row is what makes this feasible at all.** `install_post.sh` already writes `abackup` as a
wrapper, and the release already cross-compiles `supervisor` to `target/release/` for exactly the
reason `CLAUDE.md` gives — a client host never loads an image, so the binary is the deliverable. The
wrapper's body changes from `${SERVICE_INSTALL}/image/backup.sh "$@"` to
`${SERVICE_INSTALL}/supervisor backup "$@"` and nothing else about the operator surface moves.

## Shape — suggestion, planned

Four new files and one new package. The division is settled by two facts about the existing code
rather than by taste.

**`probe` exports five functions and zero types.** `Create`, `RunPoll`, `RunCycle`, `Leading`,
`Resign` — every one a verb the engine calls, and no type crosses the boundary in either direction.
That is the interaction to be consistent with.

**`backup.md`'s own boundary table already assigns the stage work to the probe**: `probe_impl_backup.go`
owns "when to run, discovering the modules, ordering and timing the stages, **the `/share` and
`/backup` copies**, deadlines, the lock, writing `status.json`". The stages were always meant to be
Go in the probe; `backup.sh` is the temporary holder of work already allocated.

| File | Holds |
|---|---|
| `internal/backup/` | **new leaf package** — the run tree and its documents, imported by both `probe` and `engine` |
| `internal/backup/backup_document.go` | the four document shapes, their atomic write and read — the contract now in `backupDocument`'s doc comment |
| `internal/backup/backup_tree.go` | run/stage/service/scrub paths, the run-id stamp and its parse, the snapshot reader and fingerprint |
| `internal/backup/backup_state.go` | the one state-resolution rule, replacing `backup_resulted` **and** `backupResolvedState` |
| `internal/probe/probe_util_stages.go` | the three stage bodies and their attach/detach/rsync/scrub helpers |
| `internal/engine/engine_impl_backup.go` | `RunBackupCommand` — verb dispatch, run lifecycle, lock, heartbeat, tail loop |
| `internal/engine/engine_util_render.go` | the `list` table, the progress lines, the padders |
| `cmd/cmd_backup.go` | flags, validation, `executeBackup` — the shape of `cmd_serve.go` |
| ~~`src/main/resources/image/backup.sh`~~ | deleted in the final phase, not before |

Dependencies stay one-way and acyclic: `cmd → engine → probe → backup`, and `engine → backup`.

### The stage runner is a sixth verb, not a callback

An earlier draft had `engine.init()` call `probe.SetBackupRunner(fn)`, so the probe could reach the
engine's stage bodies. **Ruled out.** Nothing in this codebase registers a callback into `probe`, the
wiring would happen invisibly as an import side effect, and it inverts the dependency in meaning even
though it compiles. `RunPoll(ctx, onPulse func(isHeartbeat bool))` shows that passing a function *as
an argument at the call site* is idiomatic here; registering one in `init()` is not the same thing.

With the stages in `probe`, no callback is needed at all. `probe` gains **one** exported verb, in the
style of the five it already has:

```go
// internal/probe — beside RunPoll, RunCycle, Create, Leading, Resign
func RunStage(ctx context.Context, request backup.StageRequest) error
```

One implementation, two callers, and they are the two triggers that already exist:

```go
// engine_impl_backup.go — a hand run, supervisor backup start --stage tertiary
if err := probe.RunStage(ctx, request); err != nil { ... }

// probe_impl_backup.go cycle() — the scheduled run, replacing exec.CommandContext("bash", p.runner, ...)
if err := RunStage(ctx, backup.StageRequest{Stage: stage, RunID: runID, RunPath: runPath,
    Expires: expires, Trigger: metric.BackupTriggerSystem}); err != nil { ... }
```

**`RunStage` must not touch a package var `Create` sets.** `installReader` and `backupProbeInstance`
are wired by `Create`, and a hand run never calls it — no cache, no metrics, no leader. So the stage
bodies construct what they need from the config path in the request, and a test asserts `RunStage`
works on a virgin package with `Create` never called. That constraint is the whole reason the hand
run can share the scheduled run's code instead of forking it, and it is easy to break silently.

### Why not `probe_util_backup.go` as a bridge

It was the obvious candidate and it does not survive two checks.

**The log source collides.** The source is the last underscore segment, so `probe_util_backup.go`
renders `probe[backup]` — which `probe_impl_backup.go` already owns. One source per file is what
makes `--log-source` guessable from a directory listing, so the file is `probe_util_stages.go`,
rendering `probe[stages]`, and `scribe` gains `SourceProbeStages` beside the rest. That name is also
the better description: the file is the three stages, not backup-in-general.

**There is nothing left to bridge.** Once the document and tree types live in `internal/backup` and
the runner is a plain exported verb, a bridge file would hold only forwarding calls — and the
module's own rule is that a function reached from one place is a jump rather than an abstraction. The
same argument applies at file scale: a file whose content is routing is a file that will drift.

A bridge *would* be right if the stages had to stay in `engine` — then something in `probe` would
have to adapt. That is precisely the design being rejected here.

### Why `internal/backup` rather than exporting from `probe`

`engine` already imports `probe`, so the types could simply be exported there and the new package
skipped. Three reasons not to:

- **`probe` exports no types today.** Adding six exported structs changes what the package is, from a
  set of verbs to a type surface, and that is a larger change to its character than adding a package.
- **`cmd` would otherwise import `probe`** for the request type. `cmd` imports `config`, `display`,
  `metric`, `scribe` and `engine` — keeping the chain `cmd → engine → probe` intact is worth a file.
- **The document shapes are a contract with a test behind them.** A package whose entire content is
  that contract can be tested against the captured fixtures with no probe, no cache and no broker in
  scope, which is what makes the round-trip test cheap.

`metric` keeps what it already owns — the topic templates, the state vocabulary, `Payloads()` — and
`internal/backup` imports it. Nothing moves out of `metric`.

**`internal/backup` should import `metric` and nothing else — in particular it should not log.** The
existing layering is `schema ← metric ← scribe ← config ← probe ← engine`, and `stats` and `schema`
both import nothing of ours at all. A package that returns errors and lets its callers log stays in
that class, keeps its tests free of a logging harness, and cannot acquire a `Source` of its own that
nobody filters on. Every failure it can have — a malformed document, an unreadable run — is one its
caller is better placed to describe anyway, because only the caller knows which stage it was in.

### What each half owns afterwards

The split is the one `backup.md` already declares, with the shell's share handed to the probe:

| | Owns | Must not |
|---|---|---|
| `cmd/cmd_backup.go` | the grammar, flags, validation, refusals | know a stage body, a document or a topic |
| `engine_impl_backup.go` | the verb dispatch, the run lifecycle, the lock, the heartbeat, the tail, the rendering | know how a stage copies anything, or touch the metric cache |
| `probe_util_stages.go` | the three stage bodies, attach/detach, rsync, scrub, btrfs | know the schedule, the leader, the reaper, a metric or a rule |
| `probe_impl_backup.go` | unchanged — when to run, the leader, the reaper, the cluster rollup, the three metrics | execute a stage body itself |
| `internal/backup` | the run tree, the four documents, the run id, the state rule | know a probe, an engine, a mount or a broker |

If any side reaches into another's right-hand column, the split has failed — the same test
`backup.md` sets for the shell boundary it replaces.

### Files created and edited

Line counts are the current file; the estimate is after the change.

| File | Change | Consistent with |
|---|---|---|
| `internal/backup/backup_document.go` | **new**, ~200 | a leaf package like `internal/stats` or `internal/schema` — types and their I/O, no probe, no engine |
| `internal/backup/backup_tree.go` | **new**, ~250 | same; holds the path rules `stageStatusPath`/`stageStatusPaths` already express |
| `internal/backup/backup_state.go` | **new**, ~80 | a pure rule table-tested on its own, the `driveComputed`/`driveLife` shape the module already names as the exception that earns a helper — fold into `backup_document.go` if it stays this small |
| `internal/probe/probe_util_stages.go` | **new**, ~1100 | `probe_util_*` = supporting code that is not a probe, beside `probe_util_mounts.go` (585) and `probe_util_drives.go` (612) whose readers it uses |
| `internal/engine/engine_impl_backup.go` | **new**, ~700 | `engine_impl_server.go` (319) and `engine_impl_watch.go` (676) — one file per long-running entry point |
| `internal/engine/engine_util_render.go` | **new**, ~400 | `engine_util_broker.go` / `engine_util_database.go` — a facility, not a loop |
| `cmd/cmd_backup.go` | **new**, ~180 | `cmd_serve.go` (105) and `cmd_watch.go` (268) — same `init()` / `newXCmd()` / `executeX` / options-struct / `const description` shape |
| `internal/probe/probe_impl_backup.go` | **edit**, 1147 → ~800 | keeps the schedule, leader, reaper, cluster rollup and metrics; loses the run-tree types to `internal/backup` and the stage exec to `probe_util_stages.go` |
| `internal/probe/probe_impl.go` | **edit**, +6 | gains `RunStage`, the sixth exported verb beside `Create`, `RunPoll`, `RunCycle`, `Leading`, `Resign` |
| `internal/scribe/scribe_dimension.go` | **edit**, +8 | two `Source` values (`probe[stages]`, `engine[backup]`) and `SubjectStage`, added exactly as every existing source is |
| `internal/scribe/scribe.go` | **edit**, +40 | `sinkBackup()` beside `sinkFile()`/`sinkOverlay()`, and `EnableBackupAndFile` beside `EnableStdoutAndFile`/`EnableBufferAndFile` |
| `internal/config/config.go` | **edit**, +21 | three accessors beside `BackupTimeoutHours`/`BackupCommandTopic`/`BackupStateTopic`, which already exist in that exact form |
| `internal/metric/metric_schema.go` | **edit**, +8 | the scrub state enum promoted to constants, since Go will then both declare and read it |
| `src/test/python/unit/unit_test.py` | **edit**, −6 tests | the cross-language equality tests, deleted with the duplication they police |
| `install_post.sh` | **edit**, ~3 lines | the `abackup` wrapper body `image/backup.sh` → `supervisor backup`, and the `chmod +x` of the shell that no longer exists |
| `src/main/resources/image/backup.sh` | **delete**, −2295 | last, after a clean nightly cycle |

**What moves out of `probe_impl_backup.go`, symbol by symbol** — this is the bulk of the edit and it
is a move, not a rewrite: `backupDocument`, `backupSnapshot` and its `age`, `readStageDocument`,
`writeDocumentAtomic`, `readRun`, `readNewestRun`, `stageStatusPath`, `stageStatusPaths`,
`fingerprint`, `backupRunStamp`, `backupRunDirPattern` to `internal/backup`; `backupResolvedState`,
`backupTerminal`, `backupRunStarted`, `reportedForRun` to `internal/backup/backup_state.go`; and
`runStage`'s `exec.CommandContext` body to `probe_util_stages.go`. Everything else — `lead`, `reap`,
`cycle`, `armReaper`, `powerBackupDisk`, `publishHostStatus`, `backupClusterRunDecision`, the three
metric samplers — stays exactly where it is.

**Three existing tests must be retargeted rather than deleted.**
`probe_impl_backup_schema_test.go` reads `backup.sh` off disk to assert the shell and Go agree; once
there is no shell it asserts the Go writers against `metric.Payloads()` alone, which is the half that
was always doing the work. `TestProbeImplBackup_RunnerInvocationsSpeakTheRunnerCli` parses the
shell's dispatch `case` and becomes a compile-time fact, so it goes. `TestProbeImplBackup_ReaperTopicMatchesTheShell`
goes with the mirror it checks.

## The CLI — suggestion, planned

`cmd_backup.go` is a copy of `cmd_serve.go`'s shape: `init()` adds the command, a `newBackupCmd()`
builds it, `executeBackup` does the work, an options struct at the bottom, a `const` description.
Two things differ from `serve` and both are forced by the contract.

**Positional arguments, because the grammar has them.** `serve` and `watch` take none; `backup` takes
a verb and an optional argument. Cobra's idiomatic answer is subcommands, and it is **ruled out**:
`backup start` as a subcommand of `backup` would render help as `supervisor backup start [flags]`
and, worse, would let cobra reorder or reject the `--stage` flag the probe passes positionally today.
One command with `Args: cobra.MaximumNArgs(2)` and a hand-written verb switch keeps
`supervisor backup start 2026-09-22_01-00-00 --stage tertiary` parsing exactly as `backup.sh` does.
One deliberate difference: the shell collects every positional and silently ignores any past the
second, where `MaximumNArgs(2)` refuses a third. Refusing is better and it is a grammar change, so it
is declared here rather than discovered.

**`--scrub` is refused against a stage that cannot scrub, before anything else happens.** That is
`backup.sh`'s `BACKUP_SCRUB_ASKED` check and it must stay a *parse-time* refusal with exit 2, not a
runtime one.

```go
func newBackupCmd() *cobra.Command {
	opts := &backupOptions{}
	cmd := &cobra.Command{
		Use:   "backup [command] [argument]",
		Short: backupDescription,
		Long:    backupDescription,
		Args:    cobra.MaximumNArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			configPath, _ := cmd.Flags().GetString("config")
			if err := executeBackup(configPath, args, opts); err != nil {
				return fmt.Errorf("error: %w", err)
			}
			return nil
		},
	}
	cmd.Flags().StringVarP(&opts.stage, "stage", "G", backupStageAll, "execute one stage only [primary, secondary, tertiary]")
	cmd.Flags().BoolVarP(&opts.scrub, "scrub", "S", false, "scrub the backup disk, whatever the monthly window says")
	cmd.Flags().BoolVarP(&opts.quiet, "quiet", "Q", false, "drop the stdout copy of the stage log, keeping the file")
	cmd.Flags().StringVarP(&opts.timeout, "timeout-period", "T", "", "deadline for the whole run, defaulting to the configured timeout, uses unit suffixes [s, m, h]")
	addLogFlags(cmd, &opts.logOptions, "info")
	cmd.Flags().SortFlags = false
	return cmd
}
```

**Check the short letters against `cmd.go` before taking any of them.** `-v` and `-c` are persistent
on the root, and `-L/-O/-U/-A` come from `addLogFlags`, so none of those four is available. `-G` and
`-Q` are unused anywhere. `-S` and `-T` *are* used by `serve` and `watch`, for `snapshot-period` and
`trend-period`, which `backup` does not have — flags are per-command so this is legal, and it is a
deliberate choice rather than an oversight: the alternative is reaching for a letter with no
mnemonic. `--log-source=engine[backup]` then filters a run exactly as it filters a watch.

**There are no advanced flags to hide, so there is no `addAdvancedFlags` call.** With the tunables
environment-only the whole surface is four flags and the log four, which is smaller than `serve`'s.
`--help-all` survives only to print the settings table. And **no `abackup` alias on the command** —
the wrapper script is what carries that name, and a second path to the same verb is noise.

**The twenty tunables stay environment-only — no flags.** An earlier draft gave every `BACKUP_*`
setting a hidden flag defaulting from its env var. Dropped, as the largest piece of avoidable scope
in the plan:

- the contract requires the **env vars**, not flags; flags are pure addition, and each is a public
  surface to be kept and documented forever;
- nothing sets these but the probe (three of them, through `command.Env`) and an operator debugging
  once a year, both of which already work;
- it deletes the dual-parse problem with it. With flags, `--scrub-poll` should take `30s` while
  `BACKUP_SCRUB_POLL=30` must keep meaning seconds, so every duration needs `ParseDuration` with a
  `strconv.Atoi`-times-unit fallback **and a test of both spellings**. Environment-only keeps the
  shell's bare integers and one parse.

**What is worth keeping is the table, not the flags.** Declare the settings once as
`{env, unit, def, usage}` and read them in one place, exactly as `metricBuildersByID` is one table
read in one place, with a `go/ast` test asserting no `os.Getenv("BACKUP_` appears outside it — the Go
equivalent of the shell test that every setting is normalised once. `--help-all` prints that table as
documentation, which is the census the flags were really wanted for, without the surface.

## Flags and constants — what is shared, and with what — planned

**There are three existing homes for a shared value, and `backup` must use them rather than invent a
fourth.** The consolidation rule this repo already follows is that a number lives once and is *read*
by everything that needs it, including the schema.

| Home | What belongs there | Precedent |
|---|---|---|
| `config.Default*` | a value that is **both** a CLI flag default and something the schema reflector needs | `DefaultPollPeriod`/`DefaultPulseFactor` — `cmd_serve.go` defaults `--poll-period` from it, and `tools/schema/main.go` defaults its own `--poll-period` from the *same* constant, so the declared cadence cannot disagree with the running service |
| `cmd.addLogFlags` | flags several commands share | already carries `-L/-O/-U/-A` for `serve` and `watch`; `cmd_backup.go` calls it and declares none of its own |
| `internal/metric` | the published vocabularies — topics, states, `Payloads()` | `BackupState*`, `TopicBackup*`, already read by both halves |

### What `backup` contributes to each

- **`config`** gains `BackupKeepDaily/Weekly/Monthly()`, beside `BackupTimeoutHours()`,
  `BackupCommandTopic()` and `BackupStateTopic()` which already exist. The timeout needs nothing new
  — `--timeout-period` defaults to empty, meaning *take it from `config.json`*, which is where the
  deployed value already lives.
- **`internal/backup`** becomes the single home for everything the probe and the command both need
  and which is currently spelled twice: `backupRunStamp`, `backupStages`, `backupStageTertiary`, the
  run-tree path builders, `backupRunDirPattern`, and the state rule. The probe keeps only what is
  genuinely its own — `backupRunCeiling`, `backupStaleWindow`, `backupRunSkew`, `backupRunsKept`,
  `reaperIdleTicks`/`NoticeTicks`/`StaleTicks` — none of which a stage or a hand run ever reads.
- **`metric`** gains nothing but the scrub state constants, and only because Go will then read them.

### The scheduled hour has three consumers, and stays a mirror

`backupScheduledHour` is read by the probe's `cycle` (when to fire), by `auto` (pausing the reaper
only until the next scheduled run), and by **`backups.sh`, which keeps its own `BACKUPS_SCHEDULED_HOUR=1`
and stays bash**. So this one value does not collapse into a single Go constant — it remains a
cross-language vocabulary of exactly the kind the root `CLAUDE.md` governs, and keeps its mirrored
prefix and its equality test.

**Correction to *Schema strings*: five of the six equality tests die, not six.** The state
vocabulary, the three document shapes and the field readback all go with the shell that mirrored
them. The scheduled-hour test **survives, retargeted from `backup.sh` to `backups.sh`** — and today
`BACKUPS_SCHEDULED_HOUR` is checked by nothing at all, so retargeting closes a gap rather than
preserving one. `BACKUPS_TIMEOUT_DEFAULT=6` is a policy number with no Go counterpart and stays
where it is.

### The stage list is a cross-language vocabulary with no test

`generate.py:33` derives `["primary", "secondary", "tertiary"]` from the host's form factor, and Go
declares `backupStages`. Two spellings of one ordered vocabulary across a boundary that cannot share
symbols — which the root `CLAUDE.md` says must carry a mirrored prefix and an equality test that
fails loudly if either parse finds nothing. There is no such test. Add it with the port, since the
port is what makes Go the only other holder.

### One consolidation the port makes obvious but must not bundle

`cmd_serve.go` and `cmd_watch.go` declare **the same six period flags with identical usage strings**,
and `watch` hardcodes `"1s"` and `"5"` where `serve` reads `config.DefaultPollPeriod` and
`DefaultPulseFactor` — so two of watch's defaults bypass the `config.Default*` home entirely. An
`addPeriodFlags` helper beside `addLogFlags`, plus `config.DefaultWatchPollPeriod`/`WatchPulseFactor`,
would remove both the duplication and the stray literals.

**`backup` needs none of those six flags**, so it neither benefits from the change nor is blocked by
it. Do it as its own commit, before or after, and keep it out of the port's diff — the port's whole
risk profile is "did anything observable move", and touching `serve` and `watch` flag defaults in the
same change destroys that property.

## Logging — suggestion, planned

This is the sharpest tension in the task: *match watch/serve style* and *preserve the logging style*
are the same sentence pointing two ways. They are reconciled by separating the **machinery** from
the **rendering**, which is exactly what `scribe` is already built to do.

`scribe.render` is already the single renderer, and a **sink is already defined as a stamp format and
a width** — `sinkFile()` is 250 fixed, `sinkOverlay(width)` adapts. Adding `sinkBackup()` is
therefore a change in kind that `scribe` anticipates, not a special case carved out for one command.

```go
// scribe.go — beside sinkFile and sinkOverlay
func sinkBackup() sink { return sink{stamp: stampClock, layout: layoutBackup, width: 0} }
```

`layoutBackup` renders `[%-4s %-9s %8s] %s` from the same `LogLine` every other sink receives:
level (with `ERROR` shortened to `ERRS`, which is what `backup_log` already does), the **stage**, the
clock, the detail. The stage is not a new dimension — it is `Subject`, which the backup command sets
to `scribe.SubjectStage(stage)`, blank for a whole-run line exactly as `backup_marker` blanks it for
`all`.

What this buys, and it is the whole argument for doing it this way:

- **the tail output is byte-identical**, so `abackups`' `awk` banner filter, every operator's `grep`,
  and the interleaving of `backup.sh` and `backups.sh` lines all keep working;
- **`-L`, `-O`, `-U`, `-A` work on a backup run**, which they never have. `--log-subject=tertiary`
  follows one stage; `--log-level=debug` is a real debug level rather than a `set -x`;
- **the file sink is unchanged**, so a run also lands in `~/supervisor/<cmd>-<version>-pid-<pid>.log`
  with the standard 250-column layout, beside `serve`'s, for the first time;
- **`<run>/stage/<stage>/output.log` is a third sink**, per-run and per-stage, which is what the
  `tee` in `backup.sh` produces today and what `backup_finished`'s `see [...]` pointer names.

So `executeBackup` installs three handlers where `serve` installs two:

```go
logFile, err := scribe.EnableBackupAndFile(level, "backup", config.ResolvedVersion(configPath), stageLogPath, quiet, logFileSizeMB, logFileBackups, logFileAgeDays)
```

**`ERROR` goes to stderr and everything else to stdout**, which `backup_log` does today and which
`backups.sh` relies on when it discards a remote's stderr. `scribe`'s existing handlers write one
stream; `sinkBackup` needs the split, and it belongs in the handler rather than at the call site.

**Do not reach for the standard scribe columns here.** The 8-character verb, the fixed-width source
and the duration column are right for a daemon emitting thousands of similar lines; a backup run's
lines are sentences an operator reads once, and `backup.md`'s *The run's output* section is a design
in its own right. Two renderings of one record is the correct answer, and `scribe` already has two.

## Rates, ETAs and units — suggestion, planned

The layout is a contract and does not move. **The numbers inside it are measurements, not contracts,
and several are measurably wrong.** None is pinned by a test, because a rate depends on sampling
timing and no test could pin one. So this is the one area where the port should compute differently,
and each change below is listed with what it alters on screen so it is a decision rather than a
side effect.

### Integer division reports a real rate as zero

`backup_sampled` ends with `$(( delta / 1048576 / span ))` — two truncating divisions in a row, so
everything below one whole MiB per second reads `0`:

| Case | Shell | Exact |
|---|---|---|
| a mirror moving 500 KiB/s | `0` MiB/s | 0.49 MiB/s |
| 30 MiB promoted over 40 s | `0` MiB/s | 0.75 MiB/s |
| the captured scrub pair | `165` MiB/s | 165.48 MiB/s |

`backup_rated` has the same shape (`megabytes / seconds`), so a small service backup reports `0 MiB/s`
having genuinely transferred something. **That `0` is exactly the conflation the module works to
avoid**: `-` means not known and `0` means measured zero, and here a measured 0.75 renders as the
word that means nothing moved. Compute in `float64`, round once at the boundary, and the distinction
is restored for free — a true zero still renders `0`, and 0.75 renders `1`.

**On screen**: rates under 1 MiB/s change from `0` to their rounded value. Nothing else.

### Two points of twelve

The window keeps `BACKUP_RATE_POINTS` (12) samples and rates **two** of them — `sed -n 2p` against
`tail -1` — discarding the ten between. Dropping the *first* is deliberate and right (it is whatever
the counter already held, which is what made the cumulative average open at 406 MB/s). Dropping the
middle ten is not; it is what shell can do with `sed`.

A **least-squares slope over the time-stamped ring** uses every point, is unbiased under irregular
tick spacing — which is what a heartbeat competing with a wedged `statfs` actually produces — and
needs no tuning constant. It is about fifteen lines. Keep every existing rule around it: discard the
first point, reset the window when the counter moves backwards (a scrub resume or an `rsync --delete`
legitimately does), and return *not known* until three points have landed.

**On screen**: the rate is steadier and the ETA visibly stops oscillating. Same field, same width.

### The ring must stay on disk — corrected

An earlier draft had `samples` and `scrub-samples` become an in-memory ring, on the same reasoning
that retires `counters` and `disk-usage`. **That is wrong, and it would have silently broken
`abackup tail`.**

Trace who passes `backup_sampled` its `record` argument: exactly one caller does, the heartbeat
(`backup_progress "${BACKUP_RUN_PATH}" "${BACKUP_STAGE}" record`). Every other caller passes empty
and **reads** the file — including `backup_tail`, which runs in a *different process* from the stage.
So the file is not a buffer the heartbeat keeps for itself, it is the **channel by which a separate
tail process learns the rate**. `abackups tail` depends on it across six hosts. In memory, a
standalone `supervisor backup tail` would render `-` for the rate and the ETA forever, and no test
would catch it because no test pins a rate.

So `samples` and `scrub-samples` stay files, written by the stage and read by anyone. The in-memory
ring is legitimate only as a write-side cache inside the process that owns the stage. `counters` and
`disk-usage` are genuinely private — the heartbeat and the stage are their only readers and both
become goroutines — so those two still go. **The distinguishing question for every bridge file is
"does a second process read this", and it must be asked per file rather than per pattern**;
`disk-start` and `disk-device` are kept for the same reason, and `.stopped`/`.timedout` for the
stronger one that a *stop* writes them.

### Durations must come off the monotonic clock

Every span in `backup.sh` is `date +%s` arithmetic — wall clock. An NTP step mid-run corrupts a rate,
an ETA and an elapsed time at once, and the correction is invisible afterwards. Go should use
`time.Since` for every *duration* and the wall clock only for *stamps*, which is the distinction the
module already draws and already documents: `config.NowIncludingSuspend` exists precisely because
these two clocks answer different questions. The one deliberate exception is the same one the module
already names — anything measuring an **age** against a document's `started_ts` stays wall clock,
because it is comparing against a stamp somebody else wrote.

**On screen**: nothing, until a clock steps, at which point the numbers stay right instead of going
wrong silently.

### One byte type, converted only at the edge

The shell divides by `1048576` and `1073741824` at nineteen call sites and carries megabytes,
gibibytes and raw bytes in same-named variables. `backup_terabytes` even rounds by hand with a magic
`(megabytes * 10 + 524288) / 1048576`. A single `type bytes int64` with `MiB()`, `GiB()` and `TiB()`
accessors, converted only where a line is rendered, removes the whole class — and it composes with
the `reading` type already proposed for the `-` sentinel, giving one value that knows both its unit
and whether it is known at all.

**On screen**: nothing. The renderers stay byte-identical; only what feeds them is typed.

### Percentages should round, like every other percentage in supervisor

`used * 100 / sum` truncates. The module `CLAUDE.md` is explicit that **a percentage rounds to
nearest and nothing else** — that is what `stats.ConvertToInt` does for every metric — so the backup
half is the one place in the service that truncates, and it does so by accident of `$(( ))`.

**On screen**: a percentage can move by one. **This includes `disk_usage_perc` in the stage
document**, which the probe reads for `host/used_backup_space`, so the metric can move by one too.
That is the only published value this section changes, it is within the metric's own rounding, and it
makes the backup half agree with the other twenty metrics rather than disagree with them. Called out
here because it is the one change that leaves the log lines and reaches a series.

### What must not change

- **`-` means not known and `0` means measured zero.** Every improvement above must preserve it, and
  the float change strengthens it rather than weakening it.
- **The reset-on-decrease rule.** A counter that moves backwards is a fresh warm-up, in both the
  mirror and the scrub. `btrfs scrub resume` carries a cumulative total forward, so a shared helper
  must keep treating a decrease as a restart rather than as a negative rate.
- **The field order and the trailing-unknown rule** in `backup_progressed` — an unknown field at the
  end truncates the line, an unknown field in the middle holds its column with a dash. That is a
  rendering contract and it is pinned by tests.
- **The deadline clamp on the ETA.** The scrub's remaining minutes are the lesser of the rate-based
  estimate and the stage deadline, and the displayed value is usually the deadline. A better rate
  fixes the MB/s column and nothing else, which is what the module notes already say.
- **`backup_rated` stays the one place a throughput is formed.** In Go that becomes one method on the
  ring, so the sampled rate and the computed rate cannot diverge — which is the same rule, enforced
  by the type system instead of by convention.

## The port, function by function — planned

112 shell functions. Grouped by what each becomes, so the reviewer can check coverage rather than
read a hundred rows. Every name below is the shell name; the Go name is given only where it differs
in a way that matters.

### Rendering and formatting — `engine_util_render.go`

`backup_line` `backup_log` `backup_marker` `backup_banner` `backup_stopping` — become `scribe` calls
through `sinkBackup`. `backup_stopping`'s switch between `backup_log` and `backup_marker` is just
whether the subject is set.

`backup_elapsed` `backup_sized` `backup_percent` `backup_throughput` `backup_rated` `backup_megabytes`
`backup_terabytes` `backup_bar` `backup_eta` `backup_progressed` `backup_verb` `backup_rule`
`backup_row` — pure functions, one-to-one, table-tested. **These are the highest-value tests in the
whole port** and the easiest: they are total functions from strings to strings, and the shell suite
already pins their edge cases (`-` versus `0`, the padding floors, the trailing-unknown rule,
sub-terabyte tenths).

**The `-` sentinel becomes a type, and this is the one representation change worth making.** Shell
carries "not known" as the string `-` threaded through fifteen functions, and `backup.md` records
three separate incidents from confusing it with zero. In Go it is `type reading struct { value
int64; known bool }`, with the padders taking a `reading` and rendering `-` for `!known`. Every one
of those incidents becomes a compile error or a table row. **The rendered output does not change** —
that is the constraint — only the thing being rendered.

### Documents — `internal/backup`

`backup_document` `backup_scrub_document` `backup_rollup` and `primary_start`'s two inline heredocs
all become marshals of `backupDocument` and a new `backupScrubDocument`, **moved out of
`probe_impl_backup.go` into `internal/metric` or a new `internal/backup` package** so the probe and
the engine share one declaration and the word "duplicated" leaves the doc comment.

`backup_tail_field` `backup_result` — become reads of the same structs, so `jq` leaves the image's
critical path. The `jq` package dependency stays in `docker_deps_base.txt` for the module scripts.

`backup_resulted` — the one-rule state resolver, already mirrored by `backupResolvedState`. **The two
collapse into one function and that is the single clearest win of the port**: today one rule is
written twice in two languages and held equal by a test.

`backup_counters` `backup_count` `backup_field` `backup_counted` `backup_partial` `primary_counted`
`backup_transferred` `backup_total` — the counter bridge. The `counters` file and the `disk-usage`
file exist **only** because the heartbeat runs in a separate bash process that cannot see the stage's
variables. In Go both are goroutines over one mutex-guarded struct, so **the bridge files disappear**.
That is a real simplification and it is safe because nothing outside the stage directory reads them —
verified, they are named in `backup.sh` and nowhere else in the repo.

**Keep writing `disk-start`, `disk-device`, `samples`, `scrub-samples`, `.stopped` and `.timedout`.**
Those *are* read across processes — by a `stop` invocation, by a later resumed run, and by
`backup_attached`'s device check — and dropping them would break the stop path. `disk-unclean` can
go the same way as `counters` if and only if the unclean flag is set and read inside one process,
which it is; check that once more when the tertiary stage is ported.

### Process and lifecycle — `engine_impl_backup.go`

`backup_bounded` — becomes `bounded(ctx, limit, label, fn)`, and it is the load-bearing primitive. In
shell it forks a wrapper, polls for a `.rc` file and `kill -KILL`s both on expiry, leaving the orphan
behind. In Go it is a goroutine, a `select` on a `time.After`, and for an *exec* an
`exec.CommandContext` with `Cancel` sending `SIGTERM` and a `WaitDelay` — the pattern
`probe_util_drives.go` already uses for `smartctl`. It keeps `BACKUP_BOUNDED_ABANDONED` (124) as a
distinguishable outcome, because `backup_usage` branches on abandonment versus failure and that
branch is the wedge guard `CLAUDE.md` calls load-bearing.

`backup_heartbeat` `backup_settle` — a goroutine and a cancel. The `sleep` in a subshell with a
`TERM` trap, which exists only to make a bash sleep interruptible, is a `time.Ticker` and a `ctx`.

`backup_interrupt` `backup_interrupted` — `signal.NotifyContext` as `serve` uses, plus a deferred
terminal-document write. **The 143 exit code is preserved explicitly**, since Go does not exit 128+n
on its own.

`backup_sequence` — the three-stage fork loop becomes a plain `for` over stages with an in-process
call, so `set -m`, the background process group, `nohup`, `disown` and the `$0 start ... --stage`
re-exec all go. **This removes the single most fragile construct in the file.**

`backup_running` `backup_active` `backup_actives` — `pgrep -f "backup\.sh (start|stop) <run> --stage"`
has no Go equivalent and **must not be replaced by a Go process-table scan**. Replace it with a
**pidfile per stage** at `<run>/stage/<stage>/.pid` holding the pid, checked with `syscall.Kill(pid,
0)` plus a start-time match, alongside the existing document-mtime test that `backup_actives` already
uses as its other source. This is more robust than the grep, which `backup.md` notes can be defeated
by an argv that does not match, and it keeps working when the binary is renamed.

`flock` on `<root>/.lock` — already done in Go by `cycle`, reuse verbatim. The subtlety
`backup.sh` documents (the probe holds the lock across all three stages and would deadlock itself, so
`BACKUP_RUN_ID_PASSED` suppresses the per-stage lock) **disappears entirely** — one process, one lock,
taken once. Delete `BACKUP_RUN_ID_PASSED` and say so in the release notes, since it is the one
env var whose meaning does not survive.

`backup_await` `backup_tail` `backup_progress` `backup_stalled` `backup_active_stage` — the tail
loop. Straightforward, and it gets a genuine improvement for free: shell polls `status.json` every
`BACKUP_TAIL_POLL` seconds because it has no other option, where Go can poll the same way **and
should**. Do not reach for `fsnotify`: the tail also watches a pid and a wall clock, the poll is 2
seconds against multi-hour stages, and a watcher adds a dependency and a failure mode for nothing.

`backup_sampled` — the sliding rate window. Pure, table-tested, and the shell suite has six tests on
it that port directly.

### Stages — `probe_util_stages.go`

`primary_start` `primary_stop` — `docker ps`/`docker inspect` stay execs, `bash <module script>`
stays an exec with `Stdin: nil` (Go's default is `/dev/null`, which is what `</dev/null` achieves) and
no fd 9 to close, since Go never opens one.

**`*_stop` is cross-process and an earlier draft got this wrong.** It read "`pkill -CONT`/`-TERM`
becomes a signal to the tracked child pid" — true only when the stopper *is* the running process,
and `abackup stop` never is. A stop must therefore do both halves, as the shell does:

- **signal the stage**, found by its pidfile rather than by `pgrep`, and let the stage cascade
  `SIGCONT`+`SIGTERM` to the children it actually knows (its rsync, its module script). That part is
  the improvement — a known pid beats an argv pattern;
- **then run the stage's own cleanup itself, whether or not anything was alive**. `tertiary_stop`
  cancels the scrub, cancels the balance, syncs and unmounts, and it has to work after a crash with
  no process to signal. Losing that leaves `/backup` mounted and the disk powered.

So `stage_stop` stays a function a *second* process can call against a run directory, taking nothing
from the first process but the run path. A test kills a stage with `SIGKILL`, runs `stop`, and asserts
`/backup` is detached.

`secondary_start` `secondary_stop` `backup_promotion` `backup_graded` `backup_adopted` `backup_thin` —
`backup_thin`'s grandfather-father-son window is pure date arithmetic over directory names and is the
best table-test in the stage half. `date -d "<stamp>" +%G-%V` is `time.Parse` and `ISOWeek()`.

`tertiary_start` `tertiary_stop` `backup_attach` `backup_detach` `backup_detachable` `backup_reaped`
`backup_mount` `backup_declared` `backup_sourced` `backup_verified` `backup_alive` `backup_diagnosed`
`backup_attached` `backup_ready` `backup_local` `backup_shares` `backup_mounted` `backup_targets`
`backup_unclean` `backup_usage` `backup_used` `backup_bytes` `backup_expected` `backup_flushing` —
the mount and disk half, and **the reason the stages belong in `probe`**:
`probe_util_mounts.go` already parses `/proc/mounts` and `/etc/fstab` and already has `hosted()` for
rebasing under the mount root, `probe_util_drives.go` already runs `smartctl` bounded, and
`probe_util_install.go` already reads the install tree. All three are package-private neighbours, so
the stages reuse them directly rather than forcing them public for an `engine` caller. `findmnt` calls become reads of the table
that package already holds. `backup_alive`'s single-sector `dd` with `iflag=direct` becomes
`unix.Open(device, unix.O_RDONLY|unix.O_DIRECT, 0)` and one aligned 4 KiB read — **and it must stay
bounded**, because that read is precisely the one that hangs on a dead bridge.

`backup_mirroring` `backup_promoting` `backup_scrubbing` `backup_rsync` — `backup_rsync`'s
`tee`-and-`PIPESTATUS` becomes an `io.MultiWriter` over the stage log and a buffer. The rsync stats
parsing (`backup_field`'s `tr -dc '0-9'`, which is what makes `9.44M` read as `944`) ports **including
its bug-compatible behaviour**, with the shell test's expectation preserved: it is a real property of
the parser and something may depend on it.

`backup_scrub` `backup_scrub_reading` `backup_scrub_cancel` `backup_scrub_halted` `backup_scrub_corrupt`
`backup_scrub_counter` `backup_device_counter` `backup_balance` — the scrub. All `btrfs` subcommand
output parsing, all bounded, all table-testable against the captured fixtures. **Captured to
`src/test/resources/backup/`** — 43 files, read-only, one per distinct case, each carrying the command
that produced it and its exit status, because for `btrfs` and `smartctl` the exit status is half the
contract. The shell tests synthesise this input today, and synthetic fixtures are how a parser passes
its tests and fails on a real disk: the capture found three shapes nobody would have written, and two
live defects (*What the capture found*). `btrfs balance start` mutates and was not run, so the balance
parser is fixtured from a real `scrub.log` the next time one is written.

### Broker — `engine_impl_backup.go`

`backup_publish` `backup_reaper` `backup_auto` `backup_scheduled` — `mosquitto_pub`/`mosquitto_sub`
become `probe_util_broker.go`'s `brokerDial` and `brokerWatch`, which already exist, already resolve
credentials from `config.json`, and already know that only the plug command is non-retained.
`backup_publish`'s `retain` third argument becomes the same boolean the Go wrappers already take.
**This deletes the `-u supervisor -P` credential handling from the shell entirely**, which is the one
place a token could reach a process listing.

### Config — already Go

`backup_config` and its four `jq` reads (`timeout_hours`, `keep_daily`, `keep_weekly`, `keep_monthly`,
`command_topic`) are `config.Load(path)` accessors; three of the five already exist
(`BackupTimeoutHours`, `BackupCommandTopic`, `BackupStateTopic`), and `keep_*` need adding.
`backup_stages` is `config.HostStages(host)`, already there. `primary_start`'s service list is
`config.Services(host)`, already there. `secondary_start`'s share index is `config.HostIndex(host)`,
already there. **So the whole `jq`-against-`config.json` layer simply vanishes**, and with it the
warning path for a host the config does not declare, which `Config` already handles.

### What has no Go equivalent and must be designed, not translated

Four, and each is a place a careless port introduces a regression:

1. **`trap ... TERM INT` running a terminal-document write.** Go's `signal.NotifyContext` cancels a
   context; it does not run on `SIGKILL` and it races a `defer` in a goroutine. The terminal write
   must be in the **main** goroutine's `defer`, with the signal handler only cancelling, and a test
   that sends `SIGTERM` mid-stage and asserts the document reads `stopped`.
2. **`exec > >(tee -a "${BACKUP_LOG}")`.** Process substitution has no Go analogue and needs none —
   it is the third sink described above. What it *also* does is capture the stdout of every exec'd
   child into the same file, which `io.MultiWriter` on each `exec.Cmd` must reproduce, child by child.
3. **`set -m` and the background process group.** Its purpose, per the header comment, is that
   anything reading the terminal from a module script gets `SIGTTIN` rather than hanging. Go must
   reproduce it with `SysProcAttr{Setpgid: true}` on the module-script exec, and the test is the
   existing one: a module script that reads stdin must not hang.
4. **The detached start, which an earlier draft missed entirely.** An interactive
   `abackup start` does not run the stage — it re-execs itself under `nohup`, `disown`s the child,
   and then *tails* it, so Ctrl-C ends the tail and `backup_interrupt` can promise "run
   [`<id>`] continues in the background". That promise is a contract with every operator and with
   `backups.sh`, whose dispatch relies on the remote `start` returning while the run continues. Go
   must reproduce it explicitly: re-exec `os.Args[0]` with `SysProcAttr{Setsid: true}`, stdio
   redirected to the stage log, then tail the run in the parent. It is **not** enough to run the work
   in a goroutine and catch `SIGINT` — the process would die with the terminal. The guard is the same
   one the shell uses, `[ -t 1 ]`, i.e. `term.IsTerminal(int(os.Stdout.Fd()))`, plus the
   `BACKUP_TIMEOUT_HOURS = 0` case; and the re-exec must carry a marker so the child does not detach
   again, which is what `BACKUP_DETACHED` does today.
5. **`BACKUP_SOURCE_ONLY=1`.** The entire shell test suite works by sourcing the script for its
   functions. Go has no analogue and needs none — the functions are simply exported within the
   package and tested directly, which is the whole point.

## What stays shell — planned

**A module's own `src/build/resources/backup.sh`, generated by `write_container_backup` in
`src/all/_/src/build/python/asystem/container.py` and shipped by 16 modules.** It stays shell forever,
and the reason is in `backup.md`'s *Boundary with Go* table: a module's script owns what is safe to
copy and how to produce it, and its test is that it still runs by hand with no supervisor anywhere.
Nothing in this plan touches it, the `--prune-gfs` contract, or `restore.sh`.

**`backups.sh`, the cluster dispatcher — ruled out, it stays bash.** It is 247 lines, its 33 tests
pass, and its entire job is to `ssh` to each host and run `abackup` there — the work is the remote
command, not anything it computes. None of the four costs in *Why* applies to it: it declares no
vocabulary, writes no document, holds no lock and mirrors nothing in Go. It is unaffected by this
port beyond the wrapper body it dispatches changing from `backup.sh` to `supervisor backup`, and the
`awk` banner filter it wraps remote output in is preserved by the logging design above.

**So the estate keeps exactly two backup shells, and both are the right shape for shell**: a
module's own snippet, and the cluster dispatcher. What leaves is the one in the middle — the 2295
lines that were a program pretending to be a script.

## Schema strings — planned

The instruction that all schema strings live in `schema.go` is the existing rule with the shell half
removed, and it resolves cleanly because the shell half was only ever a *mirror*.

**Today** `metric_schema.go` owns `BackupState*`, `CommandOn/Off`, `AvailabilityOnline/Offline` and
every `TopicBackup*`; `backup.sh` declares `BACKUP_STATE_*`, `BACKUP_COMMAND_*` and
`BACKUP_REAPER_TOPIC` as its own copies, and `unit_test.py` holds the two sets equal. The root
`CLAUDE.md` rule for a boundary that cannot share symbols — mirror with a prefix, test for equality —
is exactly what that is.

**After** there is no boundary, so there is no mirror. Concretely:

- every `BACKUP_STATE_*` and `BACKUP_COMMAND_*` use becomes the `metric.BackupState*` /
  `metric.CommandOn|Off` constant that already exists;
- **the scrub state enum gets promoted to a constant**, because the rule that kept it a literal —
  "a vocabulary Go only declares stays a literal" — stops applying the moment Go both declares and
  reads it;
- `BACKUP_REAPER_TOPIC` becomes `metric.TopicBackupReaper()`, and every other topic the shell spells
  becomes its `metric.TopicBackup*` call;
- the four document shapes become the two structs, `metric.Payloads()` stays the declaration, and the
  test that asserts the declaration equals what the writers emit **stays and gets stronger**, since it
  now compares a marshal against a declaration rather than a heredoc against a marshal;
- `backupScheduledHour` is already a Go const; the shell's `BACKUP_SCHEDULED_HOUR` copy and the test
  holding them equal both go.

**Five equality tests in `unit_test.py` are deleted, not ported**, and that is the correct outcome: a
test whose only job is to police a duplication is finished when the duplication is. Say so explicitly
in the commit, or the next reader will read the deletion as lost coverage. **The sixth survives** —
the scheduled hour is mirrored by `backups.sh` as well, which stays bash, so that test is retargeted
rather than dropped (*Flags and constants*).

**One mirror survives and must be kept.** The module contract — `BACKUP_SKIP_HOURS`,
`BACKUP_SERVICE_RESTART`, `BACKUP_TIMEOUT_HOURS` and `--prune-gfs` — is still a boundary between Go
and 16 shell scripts that cannot share symbols. Give it the same treatment the state vocabulary has
today: named Go constants, and a test that greps the generated module script template in
`container.py` for each one and fails loudly if its own parse finds nothing.

## Tests — planned

**152 `BackupShellTest` cases port to Go, and more.** (144 at the time of writing, plus the eight
added with the two shell fixes.) The target is that every one has a named
counterpart before `backup.sh` is deleted, and the mapping is written down in the PR so a reviewer
can check coverage rather than trust it.

| Shell test group | Count | Becomes |
|---|---|---|
| pure formatters — elapsed, bar, megabytes, terabytes, sized, percent, throughput, rated, progressed, eta, row, rule | ~25 | table tests, one per function, same cases |
| parsers — `backup_field`, `backup_count`, scrub counters, device counters, balance output, `backup_declared` spec forms | ~20 | table tests against **captured production output**, not synthesised |
| state resolution — `backup_resulted`, `backup_result`, rollup counting, list verdict precedence | ~12 | one table over the six states, plus the `running` precedence cases |
| rate window — `backup_sampled`, mirroring rate, quantum, backwards counter, point bound | ~10 | table tests, the clock injected rather than stubbed |
| CLI grammar — unknown command/option/stage, scrub refusal, help, positional slots, `auto`'s argument | ~15 | `executeBackup` called directly with argv, asserting exit code and stderr |
| disk identity — verified, alive, attached, ready, detachable, diagnosed, mount refusals | ~20 | fixture tree under `src/test/resources/host/`, extended |
| usage and wedging — btrfs/df fallback, wedged path, unidentified path | ~8 | injected exec runner |
| `list` rendering | ~6 | golden-file tests on the whole table |
| process behaviour — CONT before TERM, no terminal on stdin, process group, detached run, bounded kill, fd 9 | ~10 | real subprocesses, as now |
| schema equality | 6 | **deleted** (*Schema strings*) |
| the two fixed defects | 8 | direct — they are already fixture-driven, so they port unchanged |
| everything else | ~12 | direct |

**Three test techniques the port needs and the shell suite could not have.**

- **Inject the clock.** A dozen shell tests stub `date`. In Go the backup run takes a
  `func() time.Time`, defaulted to `time.Now`, so a fourteen-hour timeout, a monthly scrub window and
  a stall detector are all tested in microseconds. `config.NowIncludingSuspend` is the existing
  precedent for the clock being a named thing rather than an implicit one.
- **Inject the exec runner.** One interface — `run(ctx, name string, args ...string) (stdout string,
  code int, err error)` — with the real implementation and a table-driven fake. Every `btrfs`,
  `rsync`, `df`, `findmnt`, `dd`, `docker`, `mount` and `umount` call goes through it. **This is the
  single decision that makes the stage half testable at all**, and without it the port ships with the
  formatters covered and the stages not.
- **Keep the real-subprocess tests real.** The signal, process-group and stdin cases must still fork
  a genuine process, because what they assert is a property of the OS, not of the code.

**New tests the shell could not express, and which justify the port:**

- a `SIGTERM` mid-stage writes a terminal document with the right cause, for each of the three stages;
- a stage whose run deadline has passed refuses and still writes a `timeout` document;
- `bounded` abandons and the caller sees `abandoned`, distinguished from failure, for every wedge
  guard;
- the counter struct under concurrent heartbeat and stage writes, under `-race` — the race the
  `counters` file exists to avoid;
- every duration setting accepts both `30` and `30s`;
- `go/ast`: no `os.Getenv("BACKUP_` outside the settings table;
- `go/ast`: no `exec.Command` outside the injected runner;
- the rate window against the captured scrub pair — the two real readings 20 s apart must rate to
  165 MiB/s, not to btrfs's own cumulative 28;
- a rate below 1 MiB/s renders its rounded value rather than `0`, and a genuine zero still renders
  `0` while an unmeasurable one renders `-`;
- the least-squares slope equals the two-point slope on a perfectly linear ring, so the change is
  provably a noise improvement rather than a different measurement;
- a counter that moves backwards truncates the window, for the mirror and for a resumed scrub alike;
- **the stage vocabulary equality test** — `generate.py`'s derived list against Go's `backupStages`,
  failing loudly if either parse finds nothing;
- **`RunStage` on a virgin package**, with `Create` never called, which is what lets a hand run share
  the scheduled run's code;
- **a stage killed with `SIGKILL`, then `stop`** — `/backup` must end detached, proving the cleanup
  half of stop does not depend on a live process;
- **the detached start** — an interactive `start` returns while the run continues, and Ctrl-C on the
  tail does not kill it;
- **a client host refuses** — `config.HostStages` empty exits 2 rather than attempting a run.

**The systest gains one case.** `fab st` already asserts against the real broker and the packaged
image; add a `--stage primary` run against the fixture tree asserting the published retained
documents. That is the one test that proves the capabilities, the device rules and the packaging
still line up, which no unit test can.

## What the capture found — built

Phase 1 is done: `src/test/resources/backup/` holds 43 files of real output from all five reachable
hosts, captured read-only on 2026-09-22, curated to one file per distinct case rather than five
copies of each shape. Its `README.md` is the index and says what each case proves. Four things came
out of it that change the plan above.

**Three shapes nobody would have synthesised**, each already documented in the module `CLAUDE.md`
and now pinned by a real file rather than by prose:

- `-d sat` against mad's Realtek bridge **exits 4, prints `Lexar SSD NM790 4TB`, and carries no ATA
  attribute table**, while `-d sntrealtek` against the same device exits 0 with an NVMe health log.
  That is the first-match-wins trap, captured from the live disk.
- `-d scsi` renders the same Crucial drive as **`CT4000MX 500SSD1`, with a space** — the 8/16-byte
  INQUIRY field split, which no hand-written fixture would contain.
- meg's Kingston carries **both** attribute 241 and 246, which is the whole reason 241 must be read
  first; mad's Crucial carries 246 alone, named `Unknown_Attribute` on this userland.

**Two live defects in `backup.sh`, both now fixed in the shell** — the two declared exceptions to the
exact-reimplementation rule. Fixing them here rather than in the port is what stops the port
inheriting a bug and the blame for it, and keeps the cutover diff free of behaviour changes:

- **A completed scrub records `progress_perc: 0`.** `documents/scrub-success.json` is a genuine
  4.4 TB success reporting zero percent, and the operator saw
  `scrub [success] at [ 0] percent having scrubbed [4416965] MiB`. A *finished*
  `btrfs scrub status` stops printing `(NN.NN%)`, so the final reading parses as zero; the
  `[ "${progress%%.*}" -eq 0 ] && progress="${reached:-0}"` guard exists to catch exactly this and
  does not, because `reached` is captured **after** the final zero reading rather than before it.
  **Fixed**: `reached` is declared with the other locals and updated inside the loop before the
  finishing read can overwrite it, and the in-loop log line and document render from it — so a run
  also stops logging a spurious `0 percent` on its last tick.
- **The percentage legitimately exceeds 100.** The same run logged `100.08` then `100.15`, because
  btrfs rates a resumed pass against the whole filesystem. **Fixed**: clamped in
  `backup_scrub_reading` at the source, so the log line and the `progress_perc` field agree and
  `backup_percent` stays a pure padder, carrying no policy.

Both fixes were verified to bite — reverted, the new tests fail with `0 != 98.44` and
`'100.15' != '100'`, which is exactly what production produced. `shellcheck -x` is clean and all 152
`BackupShellTest` cases pass on a GNU userland.

**The running-scrub rendering was captured too, and how matters.** It only exists while `/backup` is
mounted, and the reaper powers the disk down between runs. With `/backup` mounted on max, whose pass
was already `aborted`, it was resumed for 40 seconds and cancelled — returning the disk to the same
`aborted` state having completed ~6.8 GB more of the scrub, which is work its next run would have
done anyway. Retake them the same way, and only against a pass that is already aborted.

The pair 20 seconds apart is the useful part: `data_bytes_scrubbed` moved 3.23 GiB between them,
about 165 MiB/s, while btrfs's own `Rate:` field read 28.25 MiB/s — a cumulative average over the
whole 9h55m pass. That is live evidence for why `backup_sampled` rates a sliding window instead of reading
`Rate:`, and it is now a fixture rather than an assertion in a document.

## Open questions and rollback — planned

Four things this plan does not settle, flagged rather than hidden.

**There is no way back from a bad night, and there should be.** Phases 5 and 6 replace the stages
that can destroy data, and the plan's only safety is that `backup.sh` still exists until phase 7 —
which is no use at 01:00 when the Go tertiary has done something wrong. Add a
`BACKUP_IMPL=shell|go` switch for the duration of phases 4-6, read once at the top of `RunStage` and
defaulting to `shell` until each stage has proven a week, so reverting a host is an env var in its
`.env_all` rather than a release. Delete the switch at phase 7 — a permanent one would be two
implementations forever, which is the thing being removed.

**The systest can only reach the primary stage.** The fixture host tree at `src/test/resources/host/`
has no `/backup` and cannot have one: the tertiary stage mounts a real filesystem, and the systest
runs under Docker Desktop on macOS where `rshared` propagation is already a hard failure. So the
systest gains a primary-stage run against the fixture tree and asserts the published documents;
secondary and tertiary stay covered by unit tests with an injected exec runner plus the
shadow-running of phases 5-6. Say this rather than implying `fab st` covers the port.

**Three shell-facing tests must survive to phase 7, not die at phase 4.** While the Go lifecycle
still execs `backup.sh` for the stage bodies, the CLI contract between them is live and needs its
test; `probe_impl_backup_schema_test.go` still reads the shell; and `BACKUP_RUN_ID_PASSED` still has
to be passed and therefore cannot be deleted. All three retire together with the file.

**The cross-process surface is the real contract and deserves its own audit.** The findings that
corrected this plan — the `samples` file, the detached start, the cross-process `stop` — were all the
same mistake: reading a file or a signal as private to one process when a second process depends on
it. Before phase 4, enumerate every file under a run directory and every signal, and record for each
which processes write and read it. That table is worth more than any test here, because each of these
would have shipped green.

## Phases — planned

Seven, each independently releasable, each leaving both implementations correct. **`backup.sh` is
deleted last and only once the estate has run a full nightly cycle on the Go path.**

| | Phase | Ends when |
|---|---|---|
| 1 | **Done.** Production fixtures captured to `src/test/resources/backup/`, 43 files, read-only, one per distinct case — see its `README.md` | the parsers have real input to be written against |
| 2 | `scribe.sinkBackup`, `SubjectStage`, `EnableBackupAndFile`; land it with `serve` unchanged | a Go line renders byte-identical to `backup_line` in a test |
| 3 | `cmd/cmd_backup.go` + `engine_impl_backup.go` with **`list`, `auto` and `help`** — and `tail`, whose rate must be read from the `samples` file rather than recomputed | `supervisor backup list` and `abackup list` produce identical bytes on every host, and a `tail` of a live shell run shows the same rate the shell does |
| 4 | The document layer, the counters, the lifecycle, `bounded`, the heartbeat, the tail loop, the detached start, and the `BACKUP_IMPL` switch — still calling `backup.sh` for the stage bodies | a Go-driven run with shell stages is indistinguishable in the run tree and on the broker |
| 5 | The primary and secondary stages in Go | a full run on one host matches a shell run's documents field for field |
| 6 | The tertiary stage, mounts and scrub in Go | a full scrubbing run on `mad` matches, including `device stats` zeroing |
| 7 | Cut over: `install_post.sh` wrapper, `probe` calls in-process, delete `backup.sh` and the six equality tests, retarget `probe_impl_backup_schema_test.go` | one full nightly cycle across all six hosts is clean |

**Phase 3 is the proof of the whole approach and should be judged ruthlessly.** If `list` and `tail`
cannot be made byte-identical — and `list` is the harder of the two, being a fixed-width table with
right-aligned columns and `-` placeholders — the logging design is wrong and it is cheap to find out
there. Diff the two outputs on a real host with real history, not in a fixture.

**Phase 4/5 run both implementations in parallel on one host.** Run the Go path under a
`BACKUP_RUN_PATH` of its own on `max` for a week beside the scheduled shell run, and diff the
documents nightly. The shadow-mode measurement in `watch.md` is the precedent, including its warning:
`scribe`'s file purge on start deletes the evidence across a release, so harvest the directory
between releases rather than disabling the purge.

## Risks and rejected alternatives — planned

- **The tertiary stage is the one that can destroy data, and it is ported last for that reason.** It
  mirrors with `--delete`, it unmounts, it snapshots, it deletes subvolumes and it zeroes device
  error counters. Every guard `backup.md` records — `backup_attached` before every share, the
  immutable bare mountpoint, `backup_alive`'s direct read, the same-filesystem refusal — must be in
  the Go before a single byte is mirrored, and the port must be diffed against the shell guard by
  guard, not merely tested.
- **A one-process design makes a wedge fatal where it used to be survivable.** Addressed by
  `bounded` and by every hardware-touching syscall running in its own goroutine, but it is the
  standing risk of the whole change and deserves a line in the module `CLAUDE.md` afterwards.
- **Cobra subcommands for the verbs** — ruled out, above: it changes the grammar `install_post.sh`,
  `backups.sh` and the probe all pass through.
- **Putting the stage bodies in `engine`** — ruled out, and this reversed an earlier draft. They need
  the mount reader, the drive reader and the install reader, all package-private in `probe`, so an
  `engine` home would force a dozen symbols public to buy nothing; and `backup.md`'s boundary table
  already assigns "the `/share` and `/backup` copies" to the probe. `internal/backup` is scoped to
  the run tree and its documents alone, which needs none of those.
- **A callback registered into `probe` from `engine.init()`** — ruled out, see *The stage runner is a
  sixth verb*. No precedent, invisible wiring, and unnecessary once the stages sit beside the readers
  they use.
- **Rewriting the run tree, the document shapes or the topic layout while we are in there** — ruled
  out, and it is the likeliest way this goes wrong. Every one of them is a published vocabulary with
  live retained data behind it, and the root `CLAUDE.md` is explicit that renaming one is a data
  migration. If a shape is wrong, fix it in a release of its own, after this one lands.
- **Dropping `pgrep` for a Go process scan** — ruled out in favour of pidfiles, above. A scan of
  `/proc` for a matching argv is the same fragility in a second language.
- **Keeping `backup.sh` as a thin shim that calls the Go** — ruled out. Two entry points for one job
  is what this plan exists to remove, and the shim would still need the argument parsing, which is
  where three of the recorded bugs were.
