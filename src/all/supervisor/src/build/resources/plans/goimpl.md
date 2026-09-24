# Goimpl

**Built.** `src/main/resources/image/backup.sh` (2295 lines of bash) is replaced by native Go:
`internal/probe`'s `probe_util_backup*.go` — the run tree, the four documents, the state rule and the
stage bodies — driven from two sides by `probe_impl_backup.go` (the 01:00 schedule) and
`cmd/cmd_backup.go` (the `supervisor backup` command), which reaches it through
`internal/engine/engine_impl_backup.go` — a façade of type aliases over probe's backup vocabulary, so
`cmd` imports `engine` alone and no second command enum exists. It
lived in its own package for a while; `probe` is the only package that can host it, because the backup
probe owns three metrics and must read the run tree to compute them. There is no shell fallback and no `BACKUP_IMPL` switch: the Go path is the
only path, for the scheduled `serve` cycle and a hand `supervisor backup start` alike.
`install_post.sh`'s `abackup` wrapper execs the Go binary (`${SERVICE_INSTALL}/supervisor backup
"$@"`, sourcing `.env` first so broker and timeout overrides still reach it).

What the backup system *does* — the run tree, the document shapes, the mount-identity guards, the
reaper, the GFS thinning, the scrub procedure — is `backup.md`, and none of it was re-decided here.
This file holds only what the port itself settled.

## Verdicts, and the mechanism behind each

**Cut over directly, with no phased rollout and no shadow mode.** A `BACKUP_IMPL=shell|go` switch
defaulting to shell was built and then removed in the same session, on instruction. Verification was
real-host read-only checks plus production testing by the operator afterwards, rather than a week of
shadow-running. This was the single biggest risk in the work, taken deliberately; it is recorded
because a reader finding no rollout ramp should know it was a decision, not an omission.

**Stop is marker-file-polled, never pidfile-and-SIGTERM.** For a *scheduled* run `RunStage` executes
as a goroutine inside the long-running `serve` daemon, so a pidfile holds the daemon's own pid —
signalling it would trip `cmd_serve.go`'s graceful shutdown and stop every host's backups and the
daemon with them, not the one stage. `StopStage` writes a `.stopped` marker in the stage directory
and `RunStage`'s background poller cancels itself on seeing it. That works identically whether the
stopper is a separate process or the same one, and leaves no signal path to get wrong.

**The live progress line was dropped and then restored.** The first cut reported stage progress only
through `scribe`'s per-share and per-stage lines, which is materially less information during a
multi-hour tertiary stage than the shell's ten-second `mirrored [N] of [M] GiB at [R] MiB/s at [P]
percent complete`. The sampler and renderer were ported, found to have no caller, deleted — and then
put back and actually wired in: `reportMirrorProgress` ticks beside the mirror, and the scrub emits
from the poll loop it already runs. The lesson is the one the deletion nearly buried: **ported code
with no caller is a missing wiring, not dead code** — check what the original drove before removing it.

**`list` and `help` are format-faithful; `start`/`stop`/`tail`/`auto` are functionally complete but
not byte-identical.** `list`'s widths and alignment were verified against real run history on
`macmini-max`. What is deliberately not reproduced is shell's detached-start-and-follow dance
(`nohup`/`disown`/re-exec) and the incremental seen/done state machine in `backup_await`: `start`
runs its stages synchronously in the foreground, and `tail` polls, printing the row `list` would
print until the run is terminal.

**The RUN document sets `trigger`.** While shell and Go both wrote RUN documents, `trigger` came
only from `backup_rollup` on a hand run. With Go the only writer on both paths, `backup.FinishRun`
fills it from the first stage document carrying one — otherwise it would be a declared-but-unwritten
field, the phantom-value trap the root `CLAUDE.md` names.

**`BACKUP_TIMEOUT_HOURS` must be read from the environment, not only from `config.json`.**
`backups.sh`'s `backups_start_one` sets it when dispatching to `abackup start` over ssh — that is
how a cluster-wide run bounds itself to finish before the next scheduled one. The first cut of
`runBackupStart` honoured only `config.json` and `--timeout-period` and silently ignored it. The env
var now sits between the two, matching what `backup.sh` always did.

## Verification performed

Real-host, read-only checks against `macmini-max` (production, `/backup` genuinely mounted):
`findmnt`, `btrfs filesystem show`, the same-device check and a bounded direct-sector `dd` all behave
as the mount-identity code assumes — including reproducing the documented `btrfs filesystem show`
failure-to-identify quirk when a filesystem is mounted from outside the container, and confirming it
resolves once mounted from inside, which is how `mountTarget` runs in production. The cross-compiled
`linux/amd64` binary was copied into the running `supervisor` container and `supervisor backup
list`/`help` run against real run history. No mutating command (`rsync`, `mount`, `btrfs
scrub|snapshot|delete`, a real `start`) was run against production by the assistant; that half is
the operator's, deliberately.

## Testing, and what it does not claim

The 152-case shell `BackupShellTest` suite was deleted rather than ported — most of it sourced
`backup.sh` directly and could not survive it. What replaced it: document round-trips against the
nine captured production documents (`src/test/resources/backup/documents/`), the state rule as both
a table test and an exhaustive sweep over the six-word vocabulary across three stages and scrub,
every render and rate formatter (including the two bugs found live — a finished scrub's spurious
`0` percent, and progress legitimately exceeding 100%), GFS thinning, scrub-status parsing against
captured `btrfs scrub status`/`-R` output, rsync-stats parsing against captured rsync logs, and
device-stats parsing.

It does **not** claim parity with all 152 cases. Disk-identity edge cases and CLI-grammar refusals
have narrower coverage now than the shell suite gave them. `BackupsShellTest` (which tests
`backups.sh`) and `InstallPrepShellTest` are untouched and still pass.

**The shell that survives is tested where it lives.** `unit_test.py` is now three shell suites and nothing
else — `backups.sh` (the cluster dispatcher), `install_prep.sh` (the immutable `/backup` mountpoint) and
`install_post.sh` (the `abackup` wrapper, whose `set -a` + `.env` source is what carries
`BACKUP_TIMEOUT_HOURS` into the binary; a wrapper that forgets it makes the run take the configured default
silently, so the test runs the generated wrapper against a stub binary and reads back what it exported).
The systest gained the one backup assertion it can make honestly: the **packaged image** answers
`supervisor backup list`, refuses an unknown `--stage`, and no longer ships `/asystem/etc/backup.sh`.

**The module contract is pinned now.** `BACKUP_SKIP_HOURS`, `BACKUP_SERVICE_RESTART`,
`BACKUP_TIMEOUT_HOURS` and `--prune-gfs` are greped, as the Go constants that carry them, against the
per-module `backup.sh` template `container.py`'s `write_container_backup` generates; the test fails loudly
if its own parse finds no such function. Verified by planting a deliberate mismatch.

**Watch item, not churn yet:** `stageRequest` and `BackupRequest` overlap in five fields. If a third
caller ever appears, fold `stageRequest` into `{run BackupRequest; Stage; RunPath; Expires}` rather than
widening both.

**One request type, one door, validated at the boundary.** `probe.Backup(ctx, BackupRequest)` is the only
entry point, reached identically by the CLI and by the 01:00 `cycle`; `BackupPrepared` refuses an unknown
command, trigger or stage, a `--scrub` against a stage that cannot scrub and a stage against a read-only
verb, and mints the run id — all before a run directory or a lock exists. `BackupStage` and `BackupCommand`
are named types rather than strings, so a bad `--stage` fails at flag-parse time naming the three valid
words instead of surfacing as `unknown stage [x]` mid-run.

## What stays shell, and why it is right there

**A module's own `src/build/resources/backup.sh`**, generated by `write_container_backup`
(`src/all/_/src/build/python/asystem/container.py`) and shipped by every module with data to
protect. Unaffected — it is still what the primary stage execs per service, on the same contract.

**`backups.sh`, the cluster dispatcher.** Never ported and never needed to be: it declares no
vocabulary, writes no document, holds no lock, and its whole job is "ssh to each host and run
`abackup` there". The only change it needed was on the receiving end.

So the estate keeps exactly two backup shells doing real work, both the right shape for shell — a
module's own snippet and the cluster dispatcher. What left was the 2295 lines in the middle that
were a program pretending to be a script.
