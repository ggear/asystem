# cli

Replace `duf` with a Go CLI of our own — `storage`, built and laid out exactly like `supervisor` —
and give `amedia`'s `space` and `mount` commands a real implementation behind them. **planned** —
nothing here is in the repo today beyond the placeholder `main.go` and the six rendered table samples
under `src/build/resources/design/display/`. Status vocabulary: **built** is in the repo today,
**planned** is not, **ruled out** was considered and rejected on the evidence recorded beside it.

Scope is the CLI only. The publishing daemon (`storage serve` — MQTT discovery, retained per-mount
topics, InfluxDB relations, health-check fragments) is deliberately **not** in this plan; it gets its
own once the space model has proven itself. The two touch at one point only, named in
*What this does not do*.

**This CLI has no logs.** `stdout` is the only feedback: the table, or `--json`. Errors and per-host
failure reasons go to `stderr` as plain one-line sentences, and the exit status carries the verdict.
There is **no `internal/scribe`**, no `--log-level`/`--log-source`/`--log-subject`/`--log-action`, no
`slog` and no log file — supervisor needs a source/subject/action vocabulary because it is a daemon
whose work is invisible; a command that prints a table in under a second is its own log. So a failure
is reported where it happened — in the row that could not be measured — and a reason nobody can see in
the output is not worth emitting.

---

## Why not duf

`amedia space` shells out to `duf -width 250 -style ascii -output mountpoint,size,used,avail,usage`,
which means: a third-party binary that must be installed on every host and on the laptop, no estate
view (it sees one host), no notion of a `/share` subtotal or a root amalgam, and a table shape we do
not control. The three things wanted — **one row set across all hosts**, **`/` as an amalgam** and
**`/share` rolled up** — are all things `duf` cannot be asked for. Everything else it does we want,
so its *behaviour* is the specification even though its code is not the implementation.

**Read duf for three things, and take them deliberately.** First, **how it decides a mount is
interesting**: hide pseudo filesystems (`proc`, `sysfs`, `cgroup*`, `devtmpfs`, `overlay`, `squashfs`,
`tmpfs` unless asked), separate local from network (`nfs*`, `cifs`, `smbfs`, `fuse.sshfs`) from fuse,
and hide a device already shown under another mountpoint. Second, **how it renders** — a table built
by measuring every cell first and emitting once, with the glyph set as data rather than as `if`
statements at each corner (see *Display*). Third, **how it colours** — the usage figure and its bar
take a severity from the percentage and nothing else in the table is coloured (see *Colour*). The
enumeration itself we do not need to hand-roll — see *Reading the mount table*.

## Commands and flags

```
Show storage metrics

Usage:
  storage space [flags]

Aliases:
  astorage, astorages

Flags:
  -m, --mode string      mode to operate in: local, remote, auto (default [auto])
  -d, --drives string    mounts to include: comma separated list of mount globs (default [/,/share/*,/backup])
  -s, --symbols string   define output character set: auto, ascii or unicode (default [auto])
  -t, --theme string     colour theme: auto, colour or mono (default [auto])
  -j, --json             output json not tabular text
  -h, --help             help for space
```

`storage mount` takes over `amedia mount`'s implementation and needs no flags beyond the persistent
ones; it mounts what this host should have mounted and prints one line per mountpoint, as `amedia`
does today.

**The flag surface is supervisor's, verbatim where it overlaps** — `-m/--mode`, `-s/--symbols`,
`-t/--theme` keep the same short letters and the same vocabulary, so muscle memory carries between
`atop` and `astorage`. `cmd.Flags().SortFlags = false` and the shared `usageTemplate`/
`formatFlagUsages` from `cmd.go` are what render the `(default [x])` form above — copy `cmd.go`
wholesale rather than re-deriving it, **minus its four `--log-*` flags, `makeLevel` and the
`scribe.Vocabularies()` block in the usage footer**, which are the only parts of that file coupled to
the logging this CLI does not have.

**`--mode auto`** is `local` when this host has `/share/*` mounts and `remote` when it has none, so
`jen`, `mad`, `max`, `may` and `meg` resolve to `local` and `rue` to `remote` — the laptop asks the
estate, a server answers for itself. The test is the **mountpoint**, not the ownership: `jen`'s only
`/share/10` is a cifs mount of `mad`'s disk and it still resolves `local`, because a host that has the
path has a local question to answer, while `rue`'s SMB mounts live under `${HOME}` and it therefore has
none. (What is *rendered* is a separate question — see *A disk is rendered once, by the host that serves
it* — so `jen` local is a one-row table.)

**`--symbols auto` resolves exactly as supervisor's does**, and the resolution is a copy rather than a
restatement: unicode unless `TERM` is `linux` or `dumb` or `NO_UTF8` is set. That is the whole test in
`cmd_watch.go` and it needs no addition here.

**`--theme auto` resolves to `colour` on a terminal and `mono` otherwise** — `colour` when `stdout`
passes `term.IsTerminal`, `TERM` is neither `dumb` nor empty, and neither `NO_COLOR` nor `MONO` is set;
`mono` in every other case, which is what makes a redirect or a pipe clean without the flag.

**`auto` is answerable here in a way supervisor's is not, which is why the values differ.** Supervisor's
`--theme` is `dark`/`light` and its `auto` has to guess the terminal's *background*, which no environment
variable reports — it settles for `TERM_PROGRAM=Apple_Terminal` or an SSH session meaning light, and that
is wrong on any Mac whose profile is dark. Asking properly means writing `OSC 11` to the tty and parsing
a reply many terminals never send, on a timeout, in raw mode. `colour`/`mono` is a property of the
**output stream** instead, and "is this a terminal" is exact — so `auto` stays, it is the default, and it
never guesses.

**Ruled out — `dark`/`light` here.** The only colour is the usage severity and green/amber/red read the
same on either background, so the second palette would exist to be selected and never to differ.

**`--mode remote[mad,max]` comes free with the flag** and is worth keeping — supervisor's mode parser
already accepts the bracketed host subset, so a two-host comparison needs no new flag. Supervisor's
nine-host cap does not come with it; that is a dashboard geometry limit, not a table one.

## Layout

A Go module of its own at `src/main/go/storage` (module path `storage`), mirroring supervisor file
for file, since the repo-root rule is that there is no shared Go library across modules:

```
main.go                                        func main() { cmd.Execute() }
cmd/cmd.go                                     Execute, rootCmd, usage template, flag helpers  (from supervisor)
cmd/cmd_space.go                               newSpaceCmd, flag parsing, mode/symbols/theme resolution
cmd/cmd_mount.go                               newMountCmd
internal/config/config.go                      Load of the shipped config.json, Hosts(), Shares()
internal/engine/engine_impl_space.go           the mount table reader, the class rules and the identity fold
internal/engine/engine_impl_mount.go           what this host should have mounted, and the verdict per mountpoint
internal/engine/engine_impl_mount_darwin.go    the mount_smbfs path
internal/engine/engine_impl_mount_linux.go     the fstab path
internal/engine/engine_util_identity_darwin.go the APFS container key
internal/engine/engine_util_identity_linux.go  the source-device key
internal/engine/engine_util_backup.go          the backup run document reader
internal/engine/engine_util_fstab.go           the fstab parser
internal/engine/engine_util_remote.go          the ssh fan-out
internal/display/display.go                    the table model — rows, groups, spans
internal/display/display_table.go              the renderer and the ascii/unicode glyph sets
```

**One `internal/engine`, two `impl` files, and the file name states the role.** `engine_impl_space.go`
answers `storage space` and `engine_impl_mount.go` answers `storage mount`; `probe_impl_*`/`probe_util_*`
is supervisor's naming rule — *`impl` marks the things the package exists to provide, `util` marks
everything else* — and `engine_impl_*`/`engine_util_*` is that rule applied, exactly as supervisor's own
`engine` package applies it to its two loops. Two packages were rejected: `space` and `mount` share the
config, the fstab parser and the mountpoint-comparison rule, so splitting them puts a package boundary
through the middle of the thing they both are — *what this host's storage should be, and what it is*.
There is no spine file, for supervisor's reason in the same package: nothing is left that both `impl`
files share but the `util` files beside them.

**They stay separable inside it, and this is the line to hold**: `space` compares the mount table against
the *shipped* `config.json`, which the build parsed out of the fstab files, while `mount` acts on the
*live* `/etc/fstab` on the host it is running on — declaration at build time for the one, declaration at
run time for the other — and **`space` never mounts anything**. One package makes that a convention rather
than a compiler error, so it is worth a test: `engine_impl_space.go` must name no mount syscall and no
`exec` of `mount`, which is one `go/ast` assertion of the kind supervisor uses to police what the compiler
cannot.

**`engine_util_fstab.go` is the one file that exists for a single caller, and it earns it by being a
parser.** The repo rule is that a helper is earned by a second call site, with a pure function over a real
input space table-tested on its own as the exception — an fstab reader is exactly that, and its cases
(`PARTLABEL=`, `UUID=`, a cifs source, `nofail`, a comment, a short line) are the behaviour rather than
the implementation's shape. Everything else in the package that is used once is a **local closure
beside its use**, not a file.

**The dependency runs one way, as it does in supervisor, and this is the boundary to defend:**

| Package | Imports (internal, direct) | Role |
|---|---|---|
| `cmd` | `config`, `display`, `engine` | cobra verbs, flag resolution, and the only place that maps a reading onto a table |
| `internal/engine` | `config` | the mount table, the classes, the fold, the backup document, the fan-out, and mounting |
| `internal/display` | **nothing** | the table model and the renderer |
| `internal/config` | — | the shipped `config.json` |

**`display` importing nothing internal is the load-bearing part.** It takes rows of its own model, not
an `engine.Document`, so the six golden layouts are rendered from a literal table with no filesystem, no
network, no clock and no config — and `cmd` owns the one mapping between a reading and a row. The moment
`display` imports `engine` that fixture becomes a mount table and the renderer's tests start needing
plausible devices.

**Two build-tagged pairs, and each earns it differently.** `gopsutil` *is* the portability layer for
enumeration — that is why it was chosen over `probe_util_mounts.go` — so an `engine_impl_space_*.go` pair
would hold nothing and does not exist. `engine_util_identity_*.go` is the one thing enumeration cannot
answer portably (Linux's source device against darwin's APFS container, measured under *Reading the mount
table*), and holds the key function alone. `engine_impl_mount_*.go` is a pair for a different reason:
`mount_smbfs` against a config list and `mount` against `/etc/fstab` are two different programs, not one
program with a tag.

**The Go toolchain is not on PATH.** Build from `src/main/go/storage` with
`GOROOT=~/.goenv/versions/$GO_VERSION ~/.goenv/versions/$GO_VERSION/bin/go build ./...`; `fab b` /
`fab ut` wrap the same and also run `gofmt`, `modernize -fix` and `go vet`, which rewrite source.

**Dependencies to add to `go.mod`**: `github.com/spf13/cobra`, `github.com/spf13/pflag`,
`github.com/shirou/gopsutil/v4`, `github.com/mattn/go-runewidth`, `golang.org/x/term` and
`golang.org/x/crypto` (for `ssh`). All six are already in supervisor's graph — the first five as
direct requirements, `golang.org/x/crypto` as an indirect one at `v0.57.0` — so the versions are
known-good against the pinned toolchain. `fab pull` fetches the pinned set and only reports what could
move, so these stay put until upgraded by hand.

## Reading the mount table

**Use `gopsutil/v4`, not a hand-rolled reader.** Supervisor's own rule — *`gopsutil` is the reader
for every host resource it can answer* — applies with more force here, because this binary runs on
**macOS as well as Linux**: `disk.Partitions(false)` plus `disk.Usage(mountpoint)` answers on both,
where supervisor's `probe_util_mounts.go` parses `/proc/self/mountinfo` and is Linux-only by
construction. Do not copy that file. `duf`'s own per-OS enumeration (`unix.Getfsstat` on darwin,
mountinfo on linux) is what gopsutil is already doing underneath.

**Statfs per mount must be bounded.** The root `CLAUDE.md` rule — *bound every call that can reach
failing hardware, and treat a timeout as an answer* — is why `benchmark.sh` has `backup_bounded`, and
a `statfs` against a dead USB bridge hangs in `D` state exactly the same way. Each measurement runs
under a context timeout (2 s) on its own goroutine; a mount that times out **still commits its row**,
with `--` in every measured cell, rather than stalling the table or being silently dropped. The reason
goes to `stderr` and into the document as `state: timedout` with its `error` — there is no `Notes`
column, because the seven columns are fixed and a table that grows a column when something fails is a table whose shape
depends on the weather. `benchmark.sh` earns its `Notes` column by having no other place to put a
per-phase verdict; this one has two.

### `/` is an amalgam, and de-duplication is the whole difficulty

The estate is mid-migration — `mad` is a single btrfs pool with `root`/`home`/`var` subvolumes,
`max`/`may`/`meg` are LVM+ext4 with separate `root`, `var`, `tmp` and `home` volumes, `jen` is one
ext4 partition (`src/build/resources/plans/filesystem.md` has the measured table and the target).
So the `/` row is **the sum of every local mount on the host that is not `/share/*` and not
`/backup`**, which is one row on `jen`, four on `may`, and on `mad` three subvolumes that all report
**the same pool**.

**Summing naively triple-counts `mad`.** Btrfs subvolumes of one pool return identical
total/free from `statfs`, as do bind mounts and (under a different guise) docker's overlay mounts.
The rule is therefore: **fold mounts by their filesystem identity before summing** — the shallowest
mountpoint wins as the label, and anything that cannot be given an identity is counted once and named
in the document so the miss is visible. This is the one piece of logic that must have unit tests
against fixtures from every host shape, because it is silently wrong rather than loudly wrong.

**The identity key is per-OS, and `rue` is what proves it.** On Linux it is the source device, which is
what makes `mad` fold — measured there, `/`, `/home` and `/var` all report `/dev/nvme0n1p6`,
`414108672` blocks total and the *same* `85173100` used. On macOS the volumes of one APFS container have
**different device nodes** (`/dev/disk3s1s1`, `/dev/disk3s5`, `/dev/disk3s6`, …) and a device-keyed fold
therefore does not collapse them: measured on `rue`, seven volumes each report `1948404040` blocks total
and the same available, so summing them claims ~13 TiB of root on a 1.8 TiB disk. The key on darwin is
the **container** — the device node stripped of its volume and snapshot suffixes, `/dev/disk3s5` →
`disk3` — and it must be the container rather than the disk, because `rue` carries a second one
(`disk1`, 550 MiB, three helper volumes). So the key lives in the one build-tagged pair
`engine_util_identity_{darwin,linux}.go`, and nothing else in the package is tagged for an OS.

**Within a fold, take one member and derive `used`; never sum the members.** The two filesystems differ
in what a member reports and a single rule gets both right:

| | btrfs subvolumes (`mad`) | APFS volumes (`rue`) |
|---|---|---|
| `total` per member | identical | identical |
| `avail` per member | identical | identical |
| `used` per member | identical — the **pool's** | **its own**, summing to the container's |

Summing `used` triple-counts `mad`; taking one member's `used` understates `rue` by ~420 GiB. **`used` is
`total - avail`**, computed once per identity from any member, which is exactly what `df` prints and what
both cases agree on — 414108672 − 325309492 KiB = **84.7 GiB** on `mad` against btrfs's own 81.2 GiB (the
difference is metadata reserve), and 1948404040 − 1507859380 KiB = **420.1 GiB** on `rue` against the
394.6 + 12.7 + 10.6 + 1.9 + 0.1 = 419.9 GiB its volumes sum to. **A cross-check falls out of it**: members of one
identity must report equal `total` and `avail`, and two that do not have been mis-keyed — worth
asserting rather than trusting, since the failure is a plausible number.

**So the three columns are `size` = total, `used` = total − avail, `free` = avail**, and they add up by
construction. The consequence to know: on ext4 the root reservation counts as **used**, so the figure
reads ~1.6 % above `du` — which is what `duf` shows too, and the more useful answer to "can I still
write here".

### A disk is rendered once, by the host that serves it

**In the `/share/NN` namespace, a share is rendered only by the host that serves the device.** `mad`
mounts all eleven shares — its own three (`PARTLABEL=share_08|09|10` at `/share/10|11|12`) plus eight cifs
mounts of `max`, `may` and `meg`'s — and `design/display/ascii_local.txt` shows `mad` with **three** share
rows and a 12 TiB `/share` subtotal. That is not an omission in the sample: it is `duf`'s "hide a device
already shown under another mountpoint" raised to the estate. Rendering a cifs mount would count
`share-20` on up to six hosts, and the estate total would be arithmetic about nothing. The owner is the
host whose fstab declares a device rather than a `//host/share` source, and the fstab files say so
unambiguously.

**The rule keys on that namespace, not on the filesystem type, and `rue` is why.** A mount outside
`/share/NN` is whatever the `--drives` pattern selected, rendered as it is found — so
`astorage space --drives "${HOME}/Desktop/share/*"` on the laptop renders all eleven SMB mounts, which is
the view `media` asks for and the only storage a client has. The same disk therefore appears in `rue`'s
local table and in its server's block of the estate table, and that is correct: one is being asked about
as a **mount** ("is the share I have mounted full"), the other as a **disk** ("how full is `share_08`").
What must never happen is the same disk twice *inside one table*, which is what the namespace rule
prevents, and it is why the estate block exists only in `remote` mode where every row is a disk.

**The `/` amalgam excludes boot, firmware and recovery volumes**, which are real local filesystems and
not capacity anybody manages: `mad` carries `/boot` (ext4, 973 MiB) and `/boot/efi` (vfat, 499 MiB), `jen`
and `jil` carry `/boot/firmware`, and `rue` carries `/Volumes/Recovery` and the `disk1` trio under
`/System/Volumes`. Excluded by mountpoint prefix — `/boot`, `/efi`, `/System/Volumes`, `/Volumes` — on
top of the pseudo-filesystem hide list, and the fixtures must carry `mad`'s pair and `jen`'s one so the
`/` row stays what the samples say.

### `/backup` is read from the backup documents, never from statfs

**The backup volume is not mounted most of the time, and that is by design** — `supervisor`'s tertiary
stage powers the disk on, waits for it to enumerate, mounts it, backs up, and unmounts it again, so a
`statfs /backup` between runs measures the root filesystem the empty mountpoint sits on. A plausible
wrong number is worse than no number, so `storage` does not measure that mount at all.

Instead it reads the **most recent backup run document** supervisor has already written, which carries
the measurement taken while the disk *was* mounted:

- The run tree is `<backup home>/supervisor/backup/<run-id>/`, where run ids sort lexically
  (`YYYY-MM-DD_hh-mm-ss`) and *the backup home is supervisor's, not ours* — `/home/asystem` unless
  `BACKUP_HOME_ROOT` overrides it, which is the same pair of rules `backupRunRoot()` applies. Read the
  env var first and fall back to the constant, so a test or an exec run points somewhere harmless.
- The reading is in the **tertiary stage** document, `<run>/stage/tertiary/status.json`:
  `disk_total_mb`, `disk_used_mb` and `disk_usage_perc`. Size and used come from the first two, and
  free is `total - used` as everywhere else; `disk_usage_perc` is a cross-check, not the source.
- **Newest wins, and only the newest.** Walk the run directories, take the last that holds a tertiary
  document with `disk_total_mb > 0`, and stop. Do not average, do not fall back through older runs for
  a *bigger* number, and do not reconcile two runs.
- **No document, no row.** If no run has ever written one, or the newest is unparseable, or the host
  owns no backup disk at all (it has no share index, so it runs no tertiary stage), the `/backup`
  figures are **nil** — the row is omitted from the table and the mount is absent from the document. It is
  not zero, not `null` and not `--`: a host with no backup disk has nothing to say, and `jen` in the remote
  sample is exactly that case.
- **The run id and the measurement's timestamp ride with the row in the document**, since a backup figure
  is by nature a reading from the last run rather than from now; the table does not print them, because the
  estate's backup liveness is supervisor's question and it already answers it four ways.

**Ruled out — mounting `/backup` to measure it.** It spins up a disk, takes a lock supervisor owns and
turns a read-only status command into an operation on hardware. The document is the reading.

### What `--drives` selects, and which rows are summed

`--drives` replaces the default set: it is a comma-separated list of **mount globs** (`/`,
`/share/*`, `/backup` being the default, matched as anchored patterns with `*` meaning "and below"),
and the **class** of a matched mount — root-amalgam, share, backup — comes from which pattern matched
it, first match wins. A mount matching nothing is not rendered. So `--drives '/share/*'` renders shares
and nothing else, and `--drives "${HOME}/Desktop/share/*"` is how the same command works on `rue`,
where the shares are SMB mounts under a home directory.

Within a host block:

| Row | Composition |
|---|---|
| `/` | every local mount not under `/share` or `/backup`, folded by filesystem identity |
| `/share/NN` | one row per share mount, in mountpoint order |
| `/share` | the sum of the `/share/NN` rows — **only when the block carries more than one class** |
| `/backup` | the newest backup document's reading, omitted when there is none |

**A rollup is only rendered where something needs separating from something else.** A host block that
carries shares *and* a root *and* a backup gets the `/share` subtotal, because the reader is comparing
three unlike things and the subtotal is what makes the comparison; a block whose whole content is
shares does not, because the rows already are the answer and a total of everything printed is noise.
That is the difference between `design/display/ascii_local.txt` and `ascii_local_shares.txt`, and it
falls out of the `--drives` set rather than being a flag of its own. The **estate block is stronger
still — remote mode only** (see *Modes*).

`size` is the sum of totals, `used` the sum of used, and **`free` is `size - used`**, not the sum of
the available figures — ext4's reserved blocks make `avail` smaller than `total - used`, and a table
whose three columns do not add up invites exactly one bug report per reader.

## Display

`src/build/resources/design/display/` holds **six** rendered samples — `ascii_local.txt`,
`ascii_local_shares.txt`, `ascii_remote.txt` and their `unicode_*` twins — and they are the
**specification**, not sketches. They are the three cases the CLI has, in both glyph sets:

| Sample | Invocation | What it fixes |
|---|---|---|
| `*_local.txt` | `space -m local` | one host block, all three classes, the `/share` subtotal |
| `*_local_shares.txt` | `space -m local --drives '/share/*'` | one host block, shares only, **no subtotal** |
| `*_remote.txt` | `space -m remote` | one block per host plus the estate block and the grand total |

What they fix between them:

- **Seven columns under five headers.** `HOST | MOUNT | SIZE | FREE | USED`, where `USED` spans the
  last three (bytes, bar, percent). The header rule below `USED` is what splits it, so the renderer
  needs column **spans** in the header row and nothing else.
- **Host blocks with three kinds of rule.** A rule between classes inside a host starts at the `MOUNT`
  column (`│      ├───`), a rule between hosts spans the full width (`├──────┼───`), and the header
  rule is its own third form (`+======+` in ascii, `├──────┼` in unicode) — so a rule is a row type,
  not a string a renderer improvises at each corner. The `HOST` cell is printed once per block and
  blank on continuation rows.
- **Units are TiB to one decimal place**, right-aligned, throughout — no unit switching per row, since
  the point of the table is comparison down a column.
- **The bar is 20 cells**, `■` / `#`, filled `round(pct/5)`, and the percentage carries one decimal.
- **Glyphs are a `text{ascii, unicode}` pair**, exactly as `display_layout.go` does it
  (`textBar = text{ascii: "#", unicode: "■"}`), with one set for the box-drawing frame. No other
  place may spell a box character, and no corner may be chosen by an `if` at the point of emission.
- **Width is measured with `go-runewidth`**, not `len`, and every column is measured from its widest
  cell before anything is written — the renderer builds the whole model, measures it, then emits once.
  That is `duf`'s shape and it is what makes the header spans and the three rule forms land on the same
  column boundaries for free.
- **The table is the only thing on stdout.** No banner, no timing line, no "Space summary ...".

### Colour

Colour is a property of the theme, not of the glyph set — `--symbols ascii --theme colour` is a legal
and useful combination (a pipe-safe charset in a colour terminal), and `mono` emits no escapes at all.

**Only the used figures are coloured, which is `duf`'s behaviour**: the bar and the percentage take a
severity from the usage — green under 70, amber 70–90, red above 90 — and nothing else in the table,
frame included, carries an escape. The three severities are a `colourPalette`-style table indexed by
severity, in the shape `display_terminal_theme.go` already uses, so the ANSI strings are spelled once.

Two rules the samples cannot show and a test must:

- A **mono** rendering contains no `\033` anywhere, which is what makes the six samples byte-exact
  golden files rather than approximations.
- A **colour** rendering is the mono rendering with escapes inserted **only** around the bar and the
  percentage cell, so stripping escapes from it yields the mono sample exactly. That assertion is worth
  more than a second set of samples with escapes in them, which nobody can read or diff.

### Testing the renderer

**Golden layouts, in supervisor's shape.** `internal/display/display_test_layouts.go` holds one named
raw-string var per case — `displayLocalASCII`, `displayLocalSharesUnicode`, `displayRemoteASCII` and so
on — exactly as supervisor's `display_test_layouts.go` holds `displayCompactASCIISoloHost_57x10_0_3` and
its siblings, with the leading newline trimmed on comparison. The test renders a fixture set per case and
diffs against the var, so a layout regression prints as a table-against-table diff rather than as a byte
offset.

**There is no separate `design/display/<name>.txt` file any more — see Adjustments.** The named vars
in `display_test_layouts.go` are the golden copy directly; keep the fixture numbers as they are, since
they're the expected output, including `max`'s deliberate `99.9 TiB / 100.0%` row and `jen`'s
single-class block with no `/backup`.

The fixture set is a **declared table of rows**, not a live read: `display` imports nothing internal
(*Layout*), so the renderer is tested with no filesystem, no network, no clock and no config.

## `--json` is the wire format, so it is the one documented contract

`--json` is not a convenience: it is what one host sends another (*Modes*), so its shape is an agreement
between two processes that may be different versions of this binary. **One envelope serves both modes** —
`local` emits one element in `hosts`, `remote` emits one per host — so a consumer never branches on the
mode it was given, and the fan-out decodes exactly what it emits.

```json
{
  "version": "10.200.1724",
  "mode": "remote",
  "started_ts": "2026-09-26T09:14:07+08:00",
  "duration_s": 3,
  "hosts": [
    {
      "index": 1,
      "label": "mad",
      "name": "macmini-mad",
      "version": "10.200.1724",
      "state": "measured",
      "mounts": [
        {
          "mount": "/",
          "class": "root",
          "state": "measured",
          "space": {
            "size_bytes": 424047280128,
            "used_bytes": 90930360320,
            "free_bytes": 333116919808
          },
          "folded": {
            "identity": "UUID=ff55f331-1d06-4a57-a65f-89e457b3a3d0",
            "mounts": [
              "/",
              "/home",
              "/var"
            ]
          }
        },
        {
          "mount": "/share/10",
          "label": "share_08",
          "class": "share",
          "state": "measured",
          "space": {
            "size_bytes": 4095279300608,
            "used_bytes": 2919698382848,
            "free_bytes": 1175580917760
          }
        },
        {
          "mount": "/share/11",
          "label": "share_09",
          "class": "share",
          "state": "unmounted",
          "error": "declared and not mounted [/share/11] device [PARTLABEL=share_09]"
        },
        {
          "mount": "/backup",
          "label": "backup_06",
          "class": "backup",
          "state": "measured",
          "space": {
            "size_bytes": 26388279066624,
            "used_bytes": 9895604649984,
            "free_bytes": 16492674416640
          },
          "backup": {
            "run_id": "2026-09-25_01-00-00",
            "measured_ts": "2026-09-25T02:14:07+08:00"
          }
        }
      ]
    },
    {
      "index": 2,
      "label": "max",
      "name": "macmini-max",
      "state": "unreachable",
      "error": "ssh dial failed [macmini-max] [dial tcp 10.0.1.22:22 i/o timeout]"
    }
  ]
}
```

**It is printed indented, not compacted** — `json.MarshalIndent(document, "", "  ")` with a trailing
newline, so the block above *is* the output rather than a tidied rendering of it. Encoding order is struct
field order, which makes `storage space --json > before.json` a real diff rather than a reordering, and it
means a reader needs no `jq` to read one document. `jq` is then for querying, not for making the output
legible.

**Field order is identity, then version, then state, then measurements** — at every level, which is
`backupSummary`'s order (`run_id`, `state`, timestamps, then the numbers) and is what makes a `jq` dump
readable without a schema beside it. The envelope's `version` is the renderer's; a host's `version` is that
host's, which is exactly what the skew rule below reads.

**Names encode the type, by the same suffixes the backup documents use** — `_bytes`, `_s`, `_ts`, and a
bare name where the type is not in question (`label`, `mount`, `class`, `state`). Three consequences worth
stating. Sizes are **`_bytes` rather than `_mb`** because `statfs` answers in bytes and the table renders
TiB, so an `_mb` field would round twice for no reader's benefit — and a byte count is the one figure that
is neither binary nor decimal, which matters because **every unit spelled anywhere in this CLI is binary**
(below). There is **no `*_bool` anywhere**, because
every question a bool would answer here is a `state` enum with more than two answers. And there is **no
`_perc` and no `_age_s`**, because both are arithmetic over fields already present — the same reason the
rollups are absent — so the percentage is computed where it is rounded, at render time, and the age is
computed against the envelope's `started_ts`. `duration_s` stays, being wall time nobody can derive.

**`state` is the enum, and `error` is its detail.** A mount is `measured`, `unmounted` (declared in the
config, absent from the mount table) or `timedout` (the bounded statfs expired); a host is `measured` or
`unreachable`. There is deliberately **no state for a `/backup` with no run document** — that mount is
absent from the document altogether (*`/backup` is read from the backup documents*), because a reading
that has never been taken is not a mount in a state. A failed reading therefore carries **no
`space` object at all** rather than zeroed figures with an `error` beside them — a zero that means "no
answer" is the mistake `omitempty` makes on a real measurement of zero, and `backupSummary` records the
same trap. `error` is present exactly when `state` is not `measured`, and it is the same sentence `stderr`
carries.

**Nesting groups by what varies together, and every optional object is absent rather than null.** `space`
is the three figures every class answers the same way, `folded` rides on the `/` row alone and is what makes
the identity fold auditable from outside (the mounts folded and the key they folded on — the only way a
reader can catch a triple-counted pool without instrumenting the binary), and `backup` rides on `/backup`
alone because that row is a reading from the last run rather than from now.

**`label` is the drive's `PARTLABEL`, declared rather than probed.** A share row carries `share_08` and a
backup row `backup_06` — the word stamped on the partition, the key `drives.xlsx` lists per drive, and so
the one field that ties a row to a disk you can put a hand on: `/share/10` says where it is mounted this
week, `share_08` says which device it is. It comes from the shipped config, so it is present exactly when
the fstab spec is a `PARTLABEL=` and **absent when it is not** — `mad`'s `/` is declared by `UUID=`, so the
root row carries no label and its `folded.identity` holds that UUID instead. Two notes on the name:
`label` means something different one level up, where a host's is `mad`, and that is correct because each is
the identity of the object it sits on; and `index` is the host's share index, **absent on a host that owns
no share**, which is `jen` and `jil`.

**Nothing derivable is in the document.** No rollups, no estate block, no percentage, no age — every one
is arithmetic over fields already there, and a shipped copy of arithmetic is a second place for it to be
wrong. The fan-out sums per-host documents itself, and the renderer is the only thing that rounds.

**Decode leniently, compare versions loudly.** Unknown fields are ignored, missing ones take their zero,
and a host whose `version` differs from the envelope's still renders — with one line on `stderr` naming the
host and both versions. A release rolls host by host, so a mid-release fan-out is normal rather than
exceptional, and refusing to render it would make the tool useless exactly when it is most wanted.

### The doc comment, and the test that holds it true

**`engine.Document` carries the one doc comment in this module**, in the shape `backupSummary` and
`load_schema_document` use, because it is the one symbol that owns a boundary something outside the Go
depends on:

- the levels and what each one is (envelope, host, mount), then
- **one aligned spec block** giving every field, its type placeholder, the level that carries it and a
  terse note — `"label": "<text>",  MOUNT  The declared PARTLABEL, absent when the spec is a UUID` — then
- **the ownership table**: `space` writes it, the fan-out in `engine_util_remote.go` reads it, `amedia`
  reads nothing from it today, and the repo's own `storage` on another host is the only other reader.

Everything else in the module carries **no comments at all**, per the repo rule, and the three `engine`
enums (`class`, mount `state`, host `state`) are named constants beside the type rather than literals at a
call site — the vocabulary rule for a closed set of strings two pieces of code must agree on, which these
are the moment one host decodes another's document.

**A spec block restating a declaration is only safe with a test behind it**, which is the rule
`backupSummary` is held to. The declaration here is the struct tags, so the test parses the field names out
of the comment's spec block and asserts the set equals the tags reached by `reflect`, per level — and
**fails loudly if its own parse finds nothing**, so a reformat cannot quietly turn it into a no-op. That
test is worth writing; a test asserting the comment's prose is not.

## Units are binary, everywhere

**Every unit this CLI spells is a power of two, in the table and in the code alike** — TiB in the rendered
columns, GiB in any threshold, MiB where a foreign document uses it, and `1024` as the only divisor. There
is no decimal `GB` anywhere in `internal/engine` or `internal/display`, and a constant reads
`4 * 1024 * 1024 * 1024` rather than `4e9`, in the shape `benchmark.sh`'s `MIN_FREE_BYTES` already uses.

- **The table is TiB to one decimal**, `bytes / 2^40`, which is what the six samples carry — `mad`'s
  measured `/share/10` at 4 095 279 300 608 bytes renders `3.7 TiB`, where a decimal `TB` would read `4.1`
  and disagree with every other tool on the host.
- **The document carries byte counts** precisely so that the only rounding in the system happens at the
  point of display (*`--json` is the wire format*). Bytes are exact and unit-free; the moment a field is
  named for a unit, that unit is binary.
- **A foreign document's unit is converted on the way in, never relabelled.** Supervisor's backup
  documents carry `disk_total_mb`/`disk_used_mb`, and those really are **MiB** — `measureUsage` divides by
  `bytesPerMebibyte` — so the conversion is `× 1024 × 1024` and it is exact. Worth checking rather than
  assuming: a `_mb` that had meant decimal MB would have put every `/backup` row 5 % out, which is the
  kind of wrong that looks plausible forever.
- **That row's `used` is supervisor's arithmetic, not ours.** `measureUsage` prefers btrfs's own sysfs
  usage and falls back to `df --output=used`, so `used` there is the filesystem's used rather than
  `total − avail`; the `/backup` row is therefore the one row whose three figures come from a foreign
  measurement, and `free` is still derived as `size − used` so the columns add up.
- **Throughput is the one exception, and it is not a size.** `benchmark.sh` reports MB/s decimal, because
  that is how every drive and link is rated (a "10 Gbps" bus, a "3500 MB/s" NVMe), and the hardware table
  in this module's `CLAUDE.md` compares against those figures. A rate in MB/s beside a size in TiB is
  correct, not inconsistent.

## Exit status, and where a failure is reported

The table always prints. What varies is the status, and the rule is the one `amedia` needs to accumulate:

| Outcome | stdout | stderr | Exit |
|---|---|---|---|
| everything measured | the table | — | 0 |
| a mount timed out, or is declared and not mounted | the table, that row `--` | one line per row | 1 |
| a declared `/backup` with no run document | the table, no such row | one line | 0 |
| a host that declares no `/backup` (`jen`) | the table, no such row | — | 0 |
| a host unreachable in remote mode | the table, that block `--` | one line per host | 1 |
| no host reachable at all, or a flag is invalid | — | one line | 2 |
| `--json` | the document | as above | as above |

**`--` in the table and a sentence on `stderr` are the same event reported twice on purpose** — the table
is for a person, `stderr` is for the pipeline that captured it, and neither is the log this CLI does not
have. Sentences follow the repo's message conventions: the value in brackets, no `:` or dash separator —
`ssh dial failed [macmini-max] [dial tcp … i/o timeout]`, not `ssh: dial failed to macmini-max`.

## Modes

**`local`** reads this host and renders one block, and **renders no estate block and no grand total** —
a total of one host is the host, and the sample ends at its own block.

**`remote`** reads the shipped host list, collects every host, and renders every block **plus the
estate block**: `/`, `/share` and `/backup` summed across hosts, each separated by a rule, then a grand
total row with an empty `MOUNT`. That block is the one thing `remote` renders which `local` does not,
and it is rendered **only with more than one host** — a `remote` run that resolves to a single host
renders like `local`.

**The fan-out is a Go ssh client, not a shelled-out `ssh`.** `golang.org/x/crypto/ssh` dials each host
and runs the one command:

```
/var/lib/asystem/install/storage/latest/storage space -m local -d '<drives>' --json
```

**`--drives` is forwarded and nothing else is.** It selects *what is measured*, so a remote host asked for
the wrong set answers the wrong question; `--symbols` and `--theme` select *how it is rendered*, and the
remote end renders nothing, so forwarding them would be passing a flag that can only be ignored. The
default set is passed explicitly rather than left to the remote default, so the caller's version decides
what the table contains.

- **No `exec.Command("ssh", …)` anywhere.** Shelling out means a per-host process, a quoting surface
  around the remote command, `ssh`'s own stderr mixed into ours, and options (`BatchMode`,
  `StrictHostKeyChecking`, `ConnectTimeout`) passed as strings that only the remote end validates. The
  library gives a typed timeout on the dial, a typed exit status per host, `stdout` and `stderr` as
  separate readers, and a single process that the context can cancel — which is what the bounded
  parallel fan-out below actually needs.
- **Auth is the root key that already exists**, read from `~/.ssh/id_ed25519` (then `id_rsa`) with
  `ssh.ParsePrivateKey`, agent forwarding via `SSH_AUTH_SOCK` when the file is passphrase-protected.
  Passwordless root ssh to every host is how `deploy.sh` and `install_post.sh` reach hosts, so this
  needs no new mechanism, no new key and no daemon.
- **Host keys are checked against `~/.ssh/known_hosts`** via `knownhosts.New`, and an unknown host is
  that host's row failing with the reason — not a prompt, and not `InsecureIgnoreHostKey`. A CLI that
  silently accepts any key on a home LAN is still a CLI that cannot report a changed one.
- **Fan out in parallel, bounded, and never let one host hold the table.** One goroutine per host, a
  hard per-host timeout on dial *and* on the session, and a host that fails renders its block as a
  single row of `--` carrying the reason. Same verdict as the release rule: *treat a timeout as an
  answer*.
- **The local host is read in-process**, not over ssh to itself.
- **The binary is on every host already.** `storage` is an `all` module with `src/main/go/storage`,
  so `_release` cross-compiles it per target host's `GOOS`/`GOARCH` into `target/release/` — including
  a darwin/arm64 build for `rue`, which is what makes the laptop both a caller and a renderable host.
- **Host order is the label sorted**, which is what the remote sample carries (`jen`, `mad`, `max`, `may`,
  `meg`) — not `.hosts` order, which is a deployment ordering and would reshuffle the table the day a host
  moves group. The estate block is always last.
- `-m remote` with no reachable hosts is an error, not an empty table.
- **`storage mount` has no remote mode**, and that asymmetry is deliberate: measuring every host from one
  place is a report, mounting every host from one place is an operation, and `amount` over ssh is a thing
  to type on purpose rather than a flag to discover.

**Ruled out — MQTT retained topics.** The estate's own idiom (and what `atops` does) is to subscribe
to retained per-host topics, and `storage` already has the broker in `run_deps.txt`. It is rejected
*for this plan* only because it presupposes the daemon: something must publish those topics on a
cadence, which is the whole `storage serve` piece of work. When that daemon exists, remote mode
should gain MQTT as a second transport and the ssh path becomes the fallback for a host whose service
is down — the interface between `cmd_space.go` and the collector should be shaped for that now
(a `collect(hosts) (Document, error)` seam, which is also the seam the display tests stub), but the
second implementation is not written here.

**Ruled out — querying InfluxDB.** It answers with the last row written rather than the live table,
and it too presupposes the daemon.

## The shipped config

Like supervisor, `storage` ships a build-time `config.json` and reads it at runtime —
`src/build/python/storage/generate.py` writes `src/main/resources/image/config.json`, and
`internal/config` loads it with `$VAR` substitution the way `supervisor/internal/config` does. The
default path is the install tree's, exactly as `config.DefaultConfigPath` spells it —
`/var/lib/asystem/install/storage/latest/image/config.json` — and `-c/--config` overrides it, which is
what makes a checkout run against the repo's own copy without a deploy. **`storage` has no `Dockerfile`
and wants none**: it is a host-run module like `media`, so `image/` is a directory in the install tree
rather than a path inside a container, and the cross-compiled binary beside it is the whole deliverable
on every host including `rue`.

What it must carry, all of it derivable at build time from `.hosts` and the module list — **`index` first
at every level**, since it is the estate's own ordering of a host and of its shares, and **absent on a host
that owns no share**, which is `jen` and `jil`:

```json
{
  "asystem": {
    "version": "$SERVICE_VERSION_ABSOLUTE",
    "host": "$STORAGE_HOST",
    "schema": [
      {"index": 1, "host": "macmini-mad", "label": "mad", "form_factor": "server", "os": "linux", "arch": "arm64"},
      {"index": 2, "host": "macmini-max", "label": "max", "form_factor": "server", "os": "linux", "arch": "x86_64"},
      {"host": "raspbpi-jen", "label": "jen", "form_factor": "edge", "os": "linux", "arch": "arm64"}
    ]
  }
}
```

`_get_host_label`, `_get_host_index` and `HOSTS` from `fabfile` are what supervisor's `generate.py`
imports for exactly this, and `_get_modules_by_hosts` is how it decides which hosts count. Take the same
import and the same `edge`/`server` filter — and then **filter again on the domain**, `.hosts` field 3,
keeping only hosts in the same one as the host being generated for.

**That second filter is what the committed remote sample already shows, and it is not an oversight.**
`edge`+`server` is six hosts — `jen`, `jil`, `mad`, `max`, `may`, `meg` — and `ascii_remote.txt` renders
five. The missing one is `jil`, whose `.hosts` row reads `jil=raspbpi,arm64,gui,linux,edge,`: it is on the
`gui` domain, not `dar`, so a `<host>.local` fan-out from `rue` does not reach it and a block of `--`
for it on every run would be noise rather than news. Domain is the right axis because it is the thing
that decides reachability, and it is already declared.

**`rue` is deliberately *not* in that list, and renders itself in `local` mode.** It is `client`, so
supervisor's own filter excludes it and so does this one. Including it was the earlier plan and it was
wrong twice over: the laptop's only `/share` mounts are SMB mounts of other hosts' disks, which
*A disk is rendered once* excludes anyway, and its `/` is an APFS container nobody manages capacity on.
What `rue` wants is `astorage space --drives "${HOME}/Desktop/share/*"` locally — the mounted-shares view
`media` uses — and `astorages` for the estate. So the config's host list has one job, the fan-out, and
`client` hosts are absent from it while still running the binary.

### It must also carry the mount map, and one file already owns it

**The estate's mount map is declared in the repo, at `src/<host>/_<distro>_<host>/src/main/resources/fstab`**
— six files (`mad`, `max`, `may`, `meg`, `jen`, `jil`), each the fstab actually deployed to that host.
Verified against the live hosts: the checked-in files and `/etc/fstab` on all four servers agree line
for line. Every fact this module needs is in them:

| Line | What it declares |
|---|---|
| `PARTLABEL=share_08 /share/10 ext4 … nofail` | the shares this host **owns** |
| `//macmini-max/share-20 /share/20 cifs …` | who **serves** every other share, hostname and SMB name included |
| `PARTLABEL=backup_06 /backup btrfs …` | the backup mount |
| `UUID=… / btrfs subvol=root`, `/home`, `/var` | the per-host `/` amalgam expectation |

That last row confirms this beats every alternative source: on `mad` the three system lines carry
**one UUID across three subvolumes**, which is the identity fold of *Reading the mount table* stated
in the declaration. **Ruled out — shipping those system/identity lines in `config.json`** to check the
runtime fold against them: nothing ever read the shipped `system` array back (`Config.System()` had no
caller), so it was dead weight carried through the schema, the generator and the Go config for no
benefit. The runtime fold is verified against itself only (the fixtures in
`engine_impl_space_test.go`), and a declared cross-check can be reintroduced if a real drift is ever
found that fixtures alone would miss.

So `generate.py` parses those six files and emits, per host:

```json
{"index": 1, "host": "macmini-mad", "label": "mad", "form_factor": "server",
 "shares": [{"mount": "/share/10", "label": "share_08", "served_by": "macmini-mad", "smb": "share-10"},
            {"mount": "/share/20", "label": "share_06", "served_by": "macmini-max", "smb": "share-20"}],
 "backup": {"mount": "/backup", "label": "backup_06"}}
```

**`shares.csv` stays exactly as it is.** It is **generated**, not hand-maintained —
`media/src/build/python/media/generate.py` writes it from the ext4 `/share/*` lines of those same
fstab files on every `fab generate` — so it cannot drift from the owner, and `media` is its only
consumer, at four sites: `media.sh` (`move`, `mount_darwin`, completion), `deploy.sh` (the deploy host
list), the remote self-delegation bash inside `analyse.py`, and `generate.py` itself. Two generated
views of one owner is not duplication; a hand-maintained second copy would have been, which is what
made this worth checking. **Do not make `media` read `storage`'s config**, and do not add a
`storage shares` command for it — that trades a derived file for a cross-module runtime dependency
and buys nothing.

**`drives.xlsx` is not the mount declaration**, and the plan should not treat it as one. Its `Specs`
sheet does carry `Mount`/`Label` for all 11 drives and does agree with fstab, but it is hand-maintained
hardware metadata for the benchmark — vendor, NAND, enclosure, link rate — and its `Voumes` sheet is
demonstrably stale (`jen` at `/share/90`, `jil` twice at `/share/81`, where `jen`'s fstab holds one
cifs `/share/10` and nothing local). Read fstab; leave the xlsx to `benchmark.sh`.

**`rue` has no fstab in the repo**, so the laptop carries no declaration and renders purely from
observation. That is correct rather than a gap — its mounts are whatever `mount_smbfs` has attached —
and its SMB targets come from the servers' cifs lines, so nothing about `rue` needs declaring.

**Declared and observed stay separate, as everywhere else in this repo.** The config is the
declaration, the runtime mount table is the observation, and the table renders the observation. What
the declaration buys is the direction `duf` can never report — **a mount that should be there and is
not** renders as its own row saying so, which on a `nofail` estate is the difference between a share
being absent and a share being silently skipped at boot. This is the same two-direction check
`verify.sh` performs against a broker or a database.

## `storage mount`

Move `command_mount`, `mount_darwin`, `mount_linux` and `mount_active` out of `media.sh`:

- **Linux** — walk `/etc/fstab` for `/share/*` entries, skip the ones already mounted and readable,
  `mount` the rest, and print `Mount [x] already` / `Mounting [x] ... done|failed` per line as today.
  Every share is `nofail`, so a missing device is a skipped row rather than a failure.
- **macOS** — for each server host's shares, `mount_smbfs -o soft,nodatacache
  //GUEST:@<host>/share-<index> ~/Desktop/share/<index>`, creating the mountpoint first and forcing a
  `diskutil unmount` of a stale one, exactly as `mount_darwin` does now.
- The share **list** for the macOS side comes from the shipped `config.json`, whose `served_by` and
  `smb` fields are lifted straight from the servers' own cifs lines — so `//GUEST:@<host>/share-<index>`
  is read, not reconstructed, and the macOS path needs neither `shares.csv` nor a network round trip.
- Exit status is non-zero if any mount failed, as today.

**`amedia space` calls `command_mount` first, and keeps doing so.** `storage space` must **not** — a
read-only status command that mounts filesystems as a side effect is a surprise, and on `rue` it turns
a table into a network operation. An unmounted share renders as a row saying so; `storage mount` is one
word away, and `amedia space` is where the mount-then-measure sequence belongs because that is what a
media pipeline stage is for.

## What changes in `media`

**`media` keeps `space` and `mount` as commands and loses its implementations of them.** The verbs stay
where the pipeline needs them — `space` is the last stage of `process`, and `run_stage`, the usage text,
`MEDIA_COMMANDS` and the `--share` option list are all unchanged — but their bodies become one call into
the storage CLI. That is not the forwarding shim ruled out below: `amedia space` is a *pipeline stage*
with its own header, extent resolution and exit accumulation, and what it delegates is the measuring.

`command_space` loses `duf` and gains the one line, which is the `local` extent on a server:

```bash
astorage space --mode local --drives '/share/*' --symbols ascii --theme mono
```

- `--symbols ascii --theme mono` because `amedia`'s output is captured, logged and mailed, and the
  pipeline's other stages print plain text. A table with escapes in it in a log file is unreadable.
- `--drives` carries the **extent**, which is the whole reason the flag takes a list: `share|file|media`
  passes `${EXTENT_SHARE_DIR}`, `local` passes `${SHARE_DIRS_LOCAL}`, space-separated becoming
  comma-separated (`"${dirs// /,}"`). On `rue` that resolves to every mounted
  `${HOME}/Desktop/share/NN`, which is why `--drives` matches arbitrary paths rather than knowing what
  a share is.
- `-width 250 -style ascii -output …` all disappear: the column set is fixed and the width is measured.
- The `print_header` line, the `command_mount` call and the `result` accumulation are untouched.

`command_mount` loses `mount_darwin`, `mount_active` and `mount_linux` and becomes `amount`, whose
per-line output and exit status are the same, so `command_space`'s call to it is unchanged.

| Site | Change |
|---|---|
| `command_space` | replace the `duf` line with the `astorage` call, keep the rest |
| `command_mount` | replace the body with `amount`, delete `mount_darwin`, `mount_active`, `mount_linux` |
| `MEDIA_COMMANDS`, usage text, `run_stage`, `main` dispatch, `command_accepts_option` | **unchanged** |

`mount_active` is used only by `mount_linux`; confirm with a grep before deleting. Everything else that
says `mount` in `media.sh` (`command_move`'s cifs checks, the usbdrive `mount -t exfat` in `ingress`)
is unrelated and stays.

`MEDIA_SHARES_FILE` and `shares.csv` **stay**, and so do all five of their readers — `command_move`'s
host lookup, `share_indices_all`'s completion, `deploy.sh`'s host list, `analyse.py`'s generated remote
delegation and `media`'s own `generate.py` which writes it from the fstab files. Losing `mount_darwin`
removes no reader of it.

**`media` is a caller, not a copy, and nothing goes the other way.** `storage` never reads
`shares.csv`, `media` never reads `storage`'s `config.json`, and there is no `storage shares` command —
two generated views of one owner (the fstab files) is not duplication, a cross-module runtime
dependency would be.

**Ruled out — a `space` that forwards `--mode remote`.** `amedia space` is a per-host pipeline stage and
must stay `-m local`; the estate view is `astorages`, typed by a person.

## Install and wrappers

`storage` has no `install_post.sh` today; add one on supervisor's pattern, which writes wrapper
scripts rather than symlinks so the installed path is baked and `latest` is followed:

```
/usr/local/bin/astorage    -> storage                     "$@"
/usr/local/bin/astorages   -> storage space --mode remote  "$@"
/usr/local/bin/amount      -> storage mount                "$@"
```

**`astorage` passes everything through and bakes nothing**, which is what lets `amedia` call
`astorage space --mode local --drives …` verbatim and `astorage mount` work at all; `astorages` bakes
`space --mode remote` because the estate view is the thing worth one word, and it keeps the `atop`/`atops`
pairing. `--mode auto` already resolves a bare `astorage space` to `local` on a server and `remote` on
`rue`, so the baked mode on `astorages` is a shorthand rather than the only way to reach it.

`chmod +x` the binary first, as `supervisor/install_post.sh` does. On `rue` the same wrappers are
wanted; `src/rue/_macos/install.sh` is where the laptop's profile is written.

**The install path is `/var/lib/asystem/install/storage/latest/storage`** and that is what the ssh
fan-out must invoke. `deploy.sh`'s `/root/install/storage/latest/benchmark.sh` looks wrong against the
root `CLAUDE.md`'s warning about that path and is not — `/root/install` is a symlink to
`/var/lib/asystem/install` on the Linux hosts (verified on `mad`). Do not "fix" it, and do not copy
it either: the fan-out spells the real path, because `rue` has no such symlink.

## What the tests must cover, and what they must not

**Four pure functions carry the risk, and each earns its own table test** — these are the `impl`/`util`
split's payoff, since a pure function over a real input space is the one case the repo's single-call-site
rule exempts:

| Unit | Cases that matter |
|---|---|
| the identity fold | all five host shapes: `mad`'s one pool under three subvolumes, `may`'s four volumes, `jen`'s single partition, a bind mount, an unidentifiable mount counted once |
| `--drives` matching | default set, `/share/*` only, a `${HOME}` path, first-match-wins between two patterns, a mount matching nothing, an anchored `/share/1` **not** matching `/share/10` |
| the fstab parser | `PARTLABEL=`, `UUID=`, a cifs source with its host and share name, `nofail`, a comment, a short line |
| the backup document reader | newest of several runs wins, a newer run with no tertiary document falls to nothing rather than to an older run, `disk_total_mb` of zero is not a reading, an unparseable document, an empty tree |

Then three at the seams, all of them fake-driven:

- **Mode, symbols and theme resolution** — a table over the environment (`TERM`, `NO_UTF8`, `NO_COLOR`, a
  non-terminal `stdout`) and the flag string, including every invalid value returning an error. Cheap,
  and it is the part a user notices first.
- **The document round-trip** — marshal a fixture, unmarshal it, assert equality, plus the spec-block
  test above and one decode of a document carrying an unknown field and a missing field.
- **The fan-out's verdicts, against a fake collector** — a host that times out, a host returning
  malformed JSON, a host reporting a different `version`, and every-host-failing: each asserts the row
  state, the exit status and that the other hosts still rendered.

**What must not be tested, because the test would assert the implementation rather than the behaviour:**

- **Not the text of an error sentence.** Supervisor's own rule is that the `scribe` tests assert column
  *geometry* and never a message, and the same applies here — assert that a failed mount reaches `state`
  `timedout` and a non-zero exit, not that the sentence reads the way it reads today.
- **Not that something was printed.** There are no log statements to assert; `stdout` is the table and it
  is already golden-tested.
- **Not `gopsutil`, `statfs`, `ssh` or the network.** A test that dials a host proves the LAN was up. The
  collector seam is the boundary, and everything above it is tested through a fake.
- **No helper extracted only so a test could reach it.** If a step is not one of the four pure functions
  above, it is tested at the boundary of the function that calls it, and it stays a local closure.
- **No second sample set with escapes in it.** The colour assertion is "strip escapes and you get the mono
  sample" (*Colour*).

## Code style

The repo-root and `supervisor/CLAUDE.md` rules apply unchanged; the ones that will actually come up here:

- **No comments in Go source, and no empty lines inside functions or structs.** The single exception is
  `engine.Document`'s protocol doc comment above — which exists because something outside this binary
  depends on that shape, and it is held to the same test-behind-it rule.
- **Ordering within a file: the primary symbols first, the private tail last.** Exported functions (and
  `Test*` in a test file) lead, then unexported helpers, then types, then `const`/`var` blocks at the
  bottom — so a file opens on what it is for, and a reader who wants the vocabulary knows to jump to the
  end. `probe_impl_backup.go` and `cmd_watch.go` are the shape to copy.
- **A helper is earned by a second call site, and nothing else earns it, so a one-call function is
  inlined** — bodily where it is a line or two, and as a **local closure beside its use** where the step
  wants a name. The fstab parser and the four pure functions above are the exceptions the rule names (a
  pure function over a real input space, table-tested on its own), not a licence for more.
- **Every unit is binary and spelled as such** — TiB, GiB, MiB, and `1024` as the only divisor; a decimal
  `GB` in `internal/engine` or `internal/display` is a bug (*Units are binary, everywhere*).
- **Messages carry their values in brackets with no `:` or dash separator**, in errors as well as on
  `stderr`: `fmt.Errorf("invalid theme [%s]", opts.theme)`, `statfs timed out [%s] after [%s]`. Test
  assertions keep the standard `got %v want %v` idiom, which the convention exempts.
- **Table-driven tests put the expected fields at the end of the case struct, `expectedError bool` last
  and present in every case**, and a test function is `Test<File>_<Case>` with `<File>` its own file's
  name camel-cased — one prefix per file, so a failure names the file to open.

### Inline functions and closures

Supervisor's answer to "this step wants a name but has one caller" is a **local closure**, and it is a
consistent enough style to copy rather than reinvent. `cmd.go`'s `declared`, `metric_cache.go`'s `orNil`,
`truncate` and `tagsString`, `display_layout.go`'s `resize*` family and `scribe.go`'s `claim` are the
worked examples; the rules they share:

- **Declare it immediately before its first use, not at the top of the function.** `tagsString` sits
  directly above the loop that calls it, with unrelated work above that — so a reader meets the name and
  its body in the order they are needed, and a closure that drifts to the top of a long function is on its
  way to being a package-level helper nobody asked for.
- **Name it as a value, not as a procedure** — `declared`, `truncate`, `orNil`, `draw` — and give it a
  verb only when it acts (`claim`). The name carries the step; the body carries the how.
- **Parameterise what varies and capture what does not.** `declared(command, name)` takes its command as a
  parameter *because* the `PreRun` closure below it needs the same logic against a different one; a value
  that is the same at every call site is captured instead of passed. A closure with four parameters that
  all come from the enclosing scope has been written the wrong way round.
- **A one-statement body goes on one line** — `resizeIncValService := func(b *box, inc, hostCount int) { b.valLen += inc }` —
  which is what makes a family of them read as a table rather than as fifteen paragraphs.
- **A family sharing one signature is a dispatch table, and that is the strongest case for closures over
  methods.** The `resize*` set exists to be assigned into `box` fields; here it is the three rule forms and
  the per-class row builders, which are naturally `func(row) string` values selected by kind rather than a
  `switch` repeated at each emission point (*Display*).
- **A function referenced by name rather than called is a value, not a single call site.** A trap handler,
  a callback handed to another function, a `func` stored in a struct field — each is invoked by machinery
  that needs a name, so the single-call-site rule does not reach it. `benchmark.sh`'s `cleanup` (registered
  with `trap`) and `run_write` (passed to `run_col`, which runs `"$@"`) are the shell precedents, and
  `cmd.PreRun` is the Go one.
- **One or two lines used once is not a closure, it is those lines.** The global rule's "prefer repeating a
  few lines" applies inside a function too: a `func() { … }` wrapping two statements to give them a name
  costs a reader a jump for nothing.
- **A closure returns its error rather than handling it**, exactly as `typeMismatch` in
  `metric_value_data.go` returns the error the caller then wraps — there is no logging in this module to
  fall back on, so swallowing inside a closure is how a failed mount silently becomes a measured one.
- **The same applies in tests, and that is where most of them will be** — the fixture writers
  (`write := func(path string, document …)` in supervisor's backup tests) belong beside the table they
  populate, not as package-level test helpers that every later test has to read around.

## What this does not do

- **No `storage serve`**, no MQTT discovery JSON, no InfluxDB relations, no health-check fragments.
  `generate.py` keeps its single `write_schema_broker` call, which currently matches no rows.
- **No logs.** No `internal/scribe`, no `--log-*` flags, no `slog`, no log file — see the opening
  section. `stdout` is the table, `stderr` is a sentence, the exit status is the verdict.
- **No overlap with supervisor's metrics.** Supervisor already publishes `used_home_space`,
  `used_share_space`, `used_backup_space` and `failed_shares` as **percentages per host**, and those
  stay where they are. `storage` renders **per-mount detail**, which is a different question; the day
  `storage serve` exists is the day to decide whether supervisor's four rollups move, and that is a
  data migration on a published vocabulary, not a rename. The one thing `storage` *reads* from
  supervisor is the backup run document, which is a file supervisor already writes and nobody else
  owns — not a metric, not a topic, and read-only.
- **No `--output` column selection** (`duf` has one). The table's whole value is that every host is
  rendered identically; `--json` is the escape hatch for anything else.

## Build order

1. **Delete the committed binary.** `src/main/go/storage/storage` is a 2.3 MiB Mach-O built into the source
   tree by hand and committed; `fab b` builds to `target/go`, so nothing reads it and nothing should.
2. `go.mod` deps, `cmd.go` + `main.go` copied from supervisor **minus the logging flags**,
   `storage --help` renders.
3. `internal/engine` — `engine_impl_space.go` and its `util` files: enumeration, the `--drives` class
   rules, the identity fold, bounded statfs, the backup-document reader, `engine.Document` with its doc
   comment, and the four table tests. **This is
   where the plan's only real risk is.**
4. `internal/display` — the renderer, the golden layout vars and the six committed samples they are
   bound to, plus the mono/colour escape assertion.
5. `cmd_space.go` local mode + `--json`. `astorage` is useful at this point.
6. `internal/config` + `generate.py` config.json (hosts **and** the mount map parsed out of the six
   checked-in `fstab` files); `cmd_space.go` remote mode and the ssh fan-out; the declared-but-missing
   mount row.
7. `engine_impl_mount*.go` and `cmd_mount.go`, then the `media.sh` edits and the `install_post.sh` wrappers, in one change so the
   estate is never without either command.

Every step ends on `fab b` and `fab ut` from the module, since `fab b` *rewrites* source (`gofmt`,
`modernize -fix`) — read that diff rather than discovering it two steps later, and give `modernize`'s
`//go:fix inline` and `strings.Builder` fixers the look the root `CLAUDE.md` asks for.

**Then collapse this plan.** The repo rule is that a finished plan keeps the root cause, the verdicts with
the mechanism behind them, the measurements the constants rest on and any reusable procedure, and drops the
phases and the build order — and what belongs in `src/all/storage/CLAUDE.md` afterwards is the short list:
no logs, `display` imports nothing, `/backup` comes from the newest backup document, the six samples are
the golden output, and `--json` is the contract with the doc comment on it.

## Adjustments made building this

**Status at the end of this pass: steps 1–7 are all in the repo and `fab b`/`fab ut` are green** (43
tests), including a live smoke test of `storage space --mode local` against this laptop's own APFS
container and against the real generated `config.json`. Kept unresolved rather than guessed at
further: the ssh fan-out and both `mount` platform paths compile and were reviewed against the spec
but were never run against a real host, since that needs the estate reachable from this checkout.
Below is where an implementation choice had to fill in something the prose above did not pin down
precisely enough to code against, found only by reproducing the six samples byte-for-byte.

- **`src/build/resources/design/display/*.txt` no longer exists — `display_test_layouts.go` is now
  the only golden copy.** The original design put the spec in the committed `.txt` files and had a
  test assert the Go vars equal them, on the theory that "the spec in the repo and the expectation in
  the test cannot drift apart and neither becomes a third copy" (*Testing the renderer*). In practice
  that was two copies of the same nine tables (the files, and the vars generated from them) with a
  test whose only job was proving they still agreed — the vars alone are just as much "the spec, not
  a sketch" once you accept that a `_test.go` file **is** part of the repo. Deleted the directory and
  the file-comparison test (`TestDisplay_LayoutsMatchSamples` and its `designDisplayDir` helper);
  every other reference to `design/display/*.txt` elsewhere in this document is now historical.
- **The three numeric columns are fixed-width, not measured.** *Reading the mount table* and
  *Display* both describe every column as measured from its widest cell, but the six samples show
  the bytes columns holding steady at a 9-character content width (`"999.9 TiB"`) even in
  `ascii_local.txt`, whose widest actual value is 8 characters — measuring would have produced an
  10-wide cell there, not the 11 the sample carries. `bytesContentWidth` (9), `pctContentWidth` (6,
  bordered by 2 spaces rather than 1) and `barContentWidth` (20) are therefore compile-time
  constants in `display_table.go`, and a value that overflows one is clipped with `...` — the same
  posture the SQL query renderer in the root `CLAUDE.md` takes on an oversized text cell — rather
  than stretching the column. Verified with an injected 123 456.7 TiB row: every row in the table
  stayed the same total width, and the oversized cell read `123456...`. Only `HOST` and `MOUNT` are
  genuinely measured per render, since those are the columns whose content is real variable text
  rather than a fixed numeric format.
- **The bar's fill count rounds half to even, not half away from zero.** `66.7% → 13` and
  `69.2% → 14` are unambiguous, but the two exact `.5` cases in the samples disagree with ordinary
  rounding: `37.5% → 8` (rounds up) and `62.5% → 12` (rounds down). `8` and `12` are both even,
  `13.5` is not in either sample, so this is banker's rounding rather than a typo — `roundHalfEven`
  in `display_table.go` implements exactly that, and only for this one calculation.
- **The header centering bias was a symptom of an odd bytes-column width, not a real rule — fixed by
  widening the column rather than by keeping two centering functions.** At `bytesContentWidth = 9`,
  `SIZE`/`FREE` (11-wide cell, 4-char label) had an odd 7-space remainder, and `USED`'s merged span
  (43-wide, since it summed three odd-based widths) had an odd 39-space remainder — and the two
  samples split their remainders in *opposite* directions (`SIZE` right-heavy, `USED` left-heavy),
  so reproducing them byte-for-byte briefly needed two centering functions, `center` and `centerCeil`.
  Widening `bytesContentWidth` to `10` (see below) makes every one of these remainders even — `SIZE`'s
  8, `USED`'s 40 — so left and right are always equal and the bias never mattered in the first place;
  once real, `centerCeil` is gone and `center` alone is used everywhere, with no `leftHeavy` parameter.
- **The bytes columns (`SIZE`, `FREE`, the `USED` bytes sub-column) are 12 wide, not 11**, i.e.
  `bytesContentWidth = 10` rather than `9`. This was a deliberate widening (not a reproduction of any
  sample) specifically to make `SIZE`/`FREE`'s 4-char headers and `USED`'s merged span center with an
  even remainder every time, which is what let the centering bias above be deleted rather than kept.
  `"999.9 TiB"` (9 chars) is still the widest value the format ever emits, so the extra column-width
  is headroom, not a requirement — an intentional trade of one blank column-inch for simpler code.
- **The percent cell was originally a 2-space border, deliberately changed to 1.** The six samples as
  first reproduced had the percent column padded 2 spaces each side (`"   66.7%  "`, a 10-wide cell)
  while every other bordered column (bytes, bar, host, mount) used 1. That asymmetry was reproduced
  faithfully but then deliberately dropped for consistency: every column now shares one `border = 1`
  constant, and `pctContentWidth` stays `6` so `100.0%` — the maximum a percentage can ever read —
  still fits with no truncation risk. Once every column agreed on the same border, the separate
  `cellBorder`/`barBorder`/`pctBorder` constants carried no distinct value any more and were
  collapsed into the one `border` (`rightCell` also dropped its now-constant border parameter). The
  six `design/display/*.txt` samples were regenerated from the renderer itself to match (each
  percent cell is 8 wide now, not 10), and `display_test_layouts.go` was regenerated from those
  files in turn, so nothing hand-edited the samples independently of the code that produces them.
- **`HOST` was shortened to `HST`.** With every host label in the estate three characters (`jen`,
  `mad`, `max`, `may`, `meg`), the host column's width was governed entirely by the header
  (`max(len("HOST"), 3) = 4`, plus border, `= 6`); shortening the header to `HST` (3 characters, tied
  with the labels) narrows the column to 5 (`"| jen |"` instead of `"| jen  |"`) with no other
  renderer change. Regenerated the same way as the border fix above — samples from the renderer,
  `display_test_layouts.go` from the samples.
- **`config.json`'s mount map is generated by parsing the six committed `fstab` files directly** —
  `generate.py` has its own small `parse_fstab`, keyed off a `share_\d+`/`backup_\d+` regex run
  against the *identifier* column (which matches a bare `PARTLABEL=share_08` as well as an LVM path
  like `/dev/mapper/macmini--may--vg-share_04`, since the token is embedded in both forms) — this was
  necessary to reproduce `max`'s `/share/20` (`/dev/fedora_macmini-max/share_06`, no `PARTLABEL` at
  all) with the same `share_06` label `drives.xlsx` uses. A global mount→owner registry is built once
  across all six hosts from each host's *self-sourced* (non-cifs) `/share/NN` lines, then every host's
  own `shares` list (self and cifs alike) is annotated from that registry — verified against the real
  fstab files in the repo, producing exactly the eleven-share layout `ascii_remote.txt` assumes.
- **The domain filter is the hardcoded constant `dar`, not a dynamically resolved "host being
  generated for".** `generate.py` runs once from a dev checkout with no fixed identity of its own,
  and ships one `config.json` to the whole estate (the same shape supervisor already uses), so
  "the host being generated for" has no single answer at generate time. `FSTAB_DOMAIN = "dar"`
  reproduces the committed sample's five-host schema (`jen mad max may meg`, `jil` excluded) exactly;
  revisit this if a second domain of edge/server hosts is ever added.
- **The ssh fan-out has no fake-collector seam yet.** `CollectRemote` dials real hosts with
  `golang.org/x/crypto/ssh` and has no injected collector, so the fake-driven verdict tests the plan
  asks for (a host timing out, malformed JSON, a version-skewed host, every host failing) are not
  written — only compiled and read against the spec. The seam the plan names
  (`collect(hosts) (Document, error)`) is not yet factored out; `collectOneHost` is the natural seam
  to promote to an interface if those tests are added.
- **Mode/symbols/theme resolution has no dedicated test file.** It lives inline in
  `cmd_space.go` (`resolveSymbols`/`resolveTheme`) rather than as a separately tested pure function,
  so the "table over the environment" test the plan calls for under *What the tests must cover* is
  not yet written.
- **The estate rollup sums each host's own `/` and `/share` subtotal rows, not the per-share rows
  underneath.** A host missing a `/share` subtotal (single-class block) would be undercounted by the
  estate roll-up; this matches every host in the committed sample (all of which carry the subtotal)
  but is worth checking if a share-only host is ever added to remote mode.
