# cli

Replace `duf` with a Go CLI of our own — `storage`, built and laid out exactly like `supervisor` —
and move `amedia`'s `space` and `mount` commands into it. **planned** — nothing here is in the repo
today beyond the placeholder `main.go` and the two rendered table samples under
`src/build/resources/design/display/`. Status vocabulary: **built** is in the repo today,
**planned** is not, **ruled out** was considered and rejected on the evidence recorded beside it.

Scope is the CLI only. The publishing daemon (`storage serve` — MQTT discovery, retained per-mount
topics, InfluxDB relations, health-check fragments) is deliberately **not** in this plan; it gets its
own once the CLI's mount model has proven itself. The two touch at one point only, named in
*What this does not do*.

---

## Why not duf

`amedia space` shells out to `duf -width 250 -style ascii -output mountpoint,size,used,avail,usage`,
which means: a third-party binary that must be installed on every host and on the laptop, no estate
view (it sees one host), no notion of a `/share` subtotal or a root amalgam, and a table shape we do
not control. The three things wanted — **one row set across all hosts**, **`/` as an amalgam** and
**`/share` rolled up** — are all things `duf` cannot be asked for. Everything else it does we want,
so its *behaviour* is the specification even though its code is not the implementation.

**Read duf for the classification rules, not for the enumeration code.** What is worth taking is how
it decides a mount is interesting: hide pseudo filesystems (`proc`, `sysfs`, `cgroup*`, `devtmpfs`,
`overlay`, `squashfs`, `tmpfs` unless asked), separate local from network (`nfs*`, `cifs`, `smbfs`,
`fuse.sshfs`) from fuse, and hide a device that is already shown under another mountpoint. The
enumeration itself we do not need to hand-roll — see *Reading the mount table*.

## Commands and flags

```
Show storage metrics

Usage:
  storage space [flags]

Aliases:
  astorage, astorages

Flags:
  -m, --mode string      mode to operate in: local, remote (default [remote])
  -d, --drives string    mounts to include: comma separated list of mount reg-exps (default [/,/share*,/backup])
  -s, --symbols string   define output character set: auto, ascii or unicode (default [auto])
  -t, --theme string     colour theme: auto, colour or mono (default [auto])
  -j, --json             output json not tabular text
  -h, --help             help for space
```

`storage mount` takes over `amedia mount` and needs no flags beyond the persistent ones; it mounts
what this host should have mounted and prints one line per mountpoint, as `amedia` does today.

**The flag surface is supervisor's, verbatim where it overlaps** — `-m/--mode`, `-s/--symbols`,
`-t/--theme` keep the same short letters, the same vocabulary and the same `auto` resolution
(`TERM=linux|dumb` or `NO_UTF8` set ⇒ ascii; `TERM_PROGRAM=Apple_Terminal` or an SSH session ⇒ the
light/mono side), so muscle memory carries between `atop` and `astorage`. `--theme` differs only in
its values: a table is not a dashboard, so it is `colour`/`mono` rather than `dark`/`light`.
`cmd.Flags().SortFlags = false` and the shared `usageTemplate`/`formatFlagUsages` from `cmd.go` are
what render the `(default [x])` form above — copy `cmd.go` wholesale rather than re-deriving it.

## Layout

A Go module of its own at `src/main/go/storage` (module path `storage`), mirroring supervisor file
for file, since the repo-root rule is that there is no shared Go library across modules:

```
main.go                       func main() { cmd.Execute() }
cmd/cmd.go                    Execute, rootCmd, usage template, flag helpers  (from supervisor)
cmd/cmd_space.go              newSpaceCmd, flag parsing, mode/symbols/theme resolution
cmd/cmd_mount.go              newMountCmd
internal/config/config.go     Load of the shipped config.json, Hosts(), HostsByFormFactor(), Shares()
internal/scribe/scribe.go     the log source/subject/action vocabulary            (from supervisor)
internal/mount/mount_impl.go        the mount table reader and the class rules
internal/mount/mount_impl_darwin.go per-OS enumeration, build-tagged
internal/mount/mount_impl_linux.go
internal/mount/mount_util_fstab.go  fstab/expected-mount parsing, used by `storage mount`
internal/mount/mount_util_remote.go the ssh fan-out
internal/display/display.go         the table model — rows, groups, spans
internal/display/display_table.go   the renderer and the ascii/unicode glyph sets
```

`probe_impl_*`/`probe_util_*` is supervisor's naming rule — *the file name states the role* — and
`mount_impl_*`/`mount_util_*` applies it here. The log source is the last underscore segment, so
`mount_util_remote.go` logs as `mount[remote]`.

**The Go toolchain is not on PATH.** Build from `src/main/go/storage` with
`GOROOT=~/.goenv/versions/$GO_VERSION ~/.goenv/versions/$GO_VERSION/bin/go build ./...`; `fab b` /
`fab ut` wrap the same and also run `gofmt`, `modernize -fix` and `go vet`, which rewrite source.

**Dependencies to add to `go.mod`**: `github.com/spf13/cobra`, `github.com/spf13/pflag`,
`github.com/shirou/gopsutil/v4`, `github.com/mattn/go-runewidth`, `golang.org/x/term`. All five are
already pinned in supervisor, so the versions are known-good against the pinned toolchain.
`fab pull` runs `go get -u ./...` and will move them.

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
under a context timeout (2 s) on its own goroutine; a mount that times out renders `--` in its cells
with the reason in a `Notes`-style suffix rather than stalling the table or being silently dropped.

### `/` is an amalgam, and de-duplication is the whole difficulty

The estate is mid-migration — `mad` is a single btrfs pool with `root`/`home`/`var` subvolumes,
`max`/`may`/`meg` are LVM+ext4 with separate `root`, `var`, `tmp` and `home` volumes, `jen` is one
ext4 partition (`src/build/resources/plans/filesystem.md` has the measured table and the target).
So the `/` row is **the sum of every local mount on the host that is not `/share*` and not
`/backup`**, which is one row on `jen`, four on `may`, and on `mad` three subvolumes that all report
**the same pool**.

**Summing naively triple-counts `mad`.** Btrfs subvolumes of one pool return identical
total/free from `statfs`, as do bind mounts and (under a different guise) docker's overlay mounts.
The rule is therefore: **fold mounts by their filesystem identity before summing** — the device
(`st_dev` / the source device string) is the key, and the shallowest mountpoint wins as the label.
Anything that cannot be given an identity is counted once and named in the JSON so the miss is
visible. This is the one piece of logic that must have unit tests against fixtures from all five
host shapes, because it is silently wrong rather than loudly wrong.

Within a host block:

| Row | Composition |
|---|---|
| `/` | every local mount not under `/share` or `/backup`, folded by filesystem identity |
| `/share/NN` | one row per share mount, in mountpoint order |
| `/share` | the sum of the `/share/NN` rows |
| `/backup` | the backup mount |

`size` is the sum of totals, `used` the sum of used, and **`free` is `size - used`**, not the sum of
the available figures — ext4's reserved blocks make `avail` smaller than `total - used`, and a table
whose three columns do not add up invites exactly one bug report per reader.

`--drives` replaces that default set: it is a comma-separated list of **mount regexps** (`/`,
`/share*`, `/backup` being the default, matched as anchored patterns with `*` meaning "and below"),
and the class of a matched mount — root-amalgam, share, backup — comes from which pattern matched it,
first match wins. A mount matching nothing is not rendered.

## Display

`src/build/resources/design/display/unicode.txt` and `ascii.txt` are the **specification**, not
sketches. Both must be reproduced exactly, and the way to guarantee that is a table test that renders
a fixture set and diffs against those two files — the same discipline the generated schema leaves get.
Keep the fixture numbers as they are so the committed samples stay the expected output.

What the samples fix:

- **Seven columns under five headers.** `HOST | MOUNT | SIZE | FREE | USED`, where `USED` spans the
  last three (bytes, bar, percent). The header rule below `USED` is what splits it, so the renderer
  needs column **spans** in the header row and nothing else.
- **Host blocks with interior rules.** A rule between classes inside a host starts at the `MOUNT`
  column (`│      ├───`), a rule between hosts spans the full width (`├──────┼───`). The `HOST` cell
  is printed once per block and blank on continuation rows.
- **A trailing estate block** with no host label: `/`, `/share`, `/backup` summed across hosts, then
  a grand-total row with an empty `MOUNT`. It is rendered **only in remote mode with more than one
  host** — a single-host local run ends at its own block.
- **Units are TiB to one decimal place**, right-aligned, throughout — no unit switching per row, since
  the point of the table is comparison down a column.
- **The bar is 20 cells**, `■` / `#`, filled `round(pct/5)`, and the percentage carries one decimal.
- **Glyphs are a `text{ascii, unicode}` pair**, exactly as `display_layout.go` does it
  (`textBar = text{ascii: "#", unicode: "■"}`), with one set for the box-drawing frame. No other
  place may spell a box character.
- **Colour is a property of the theme, not of the glyph set** — `--symbols ascii --theme colour` is a
  legal and useful combination (a pipe-safe charset in a colour terminal). Mono emits no escapes at
  all, and `auto` resolves to mono when stdout is not a terminal, so redirection is clean without the
  flag.
- **Width is measured with `go-runewidth`**, not `len`.

Colour, when on: the percentage and bar take a severity from the usage — green under 70, amber 70–90,
red above 90 — which is `duf`'s behaviour and the only colour in the table.

## Modes

**`local`** reads this host and renders one block.

**`remote`** (the default) reads the shipped host list, fans out over ssh, and renders every block
plus the estate totals:

```
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@<host>.local \
  /var/lib/asystem/install/storage/latest/storage space -m local --json
```

- **Passwordless root ssh to every host already exists** and is how `deploy.sh` and
  `install_post.sh` reach hosts, so this needs no new mechanism and no daemon. It runs from `rue`,
  which is the point — `astorages` on the laptop is the estate view.
- **The binary is on every host already.** `storage` is an `all` module with `src/main/go/storage`,
  so `_release` cross-compiles it per target host's `GOOS`/`GOARCH` into `target/release/` — including
  a darwin/arm64 build for `rue`, which is what makes the laptop both a caller and a renderable host.
- **Fan out in parallel, bounded, and never let one host hold the table.** One goroutine per host,
  a hard per-host timeout, and a host that fails renders its block as a single row of `--` carrying
  the reason. This is the same verdict as the release rule: *treat a timeout as an answer*.
- **The local host is read in-process**, not over ssh to itself.
- `-m remote` with no reachable hosts is an error, not an empty table.

**Ruled out — MQTT retained topics.** The estate's own idiom (and what `atops` does) is to subscribe
to retained per-host topics, and `storage` already has the broker in `run_deps.txt`. It is rejected
*for this plan* only because it presupposes the daemon: something must publish those topics on a
cadence, which is the whole `storage serve` piece of work. When that daemon exists, remote mode
should gain MQTT as a second transport and the ssh path becomes the fallback for a host whose service
is down — the interface between `cmd_space.go` and the collector should be shaped for that now
(a `collect(hosts) ([]hostSpace, error)` seam), but the second implementation is not written here.

**Ruled out — querying InfluxDB.** It answers with the last row written rather than the live table,
and it too presupposes the daemon.

## The shipped config

Like supervisor, `storage` ships a build-time `config.json` and reads it at runtime —
`src/build/python/storage/generate.py` writes `src/main/resources/image/config.json`, and
`internal/config` loads it with `$VAR` substitution the way `supervisor/internal/config` does.

What it must carry, all of it derivable at build time from `.hosts` and the module list:

```json
{
  "asystem": {
    "version": "$SERVICE_VERSION_ABSOLUTE",
    "host": "$STORAGE_HOST",
    "schema": [
      {"host": "macmini-mad", "label": "mad", "index": 1, "form_factor": "server", "os": "linux", "arch": "arm64"},
      {"host": "macbook-rue", "label": "rue", "form_factor": "client", "os": "darwin", "arch": "arm64"}
    ]
  }
}
```

`_get_host_label`, `_get_host_index` and `HOSTS` from `fabfile` are what supervisor's `generate.py`
imports for exactly this, and `_get_modules_by_hosts` is how it decides which hosts count. Take the
same import and the same `edge`/`server` filter, plus `client` — `rue` must appear, since it is a host
with mounts worth rendering, which supervisor's list deliberately excludes.

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

That last row is the useful one and is why this beats every alternative source: on `mad` the three
system lines carry **one UUID across three subvolumes**, which is the identity fold of *Reading the
mount table* stated in the declaration, so the runtime fold can be checked against it rather than only
against itself.

So `generate.py` parses those six files and emits, per host:

```json
{"host": "macmini-mad", "label": "mad", "index": 1, "form_factor": "server",
 "system": [{"mount": "/", "identity": "UUID=ff55f331-…"},
            {"mount": "/home", "identity": "UUID=ff55f331-…"},
            {"mount": "/var", "identity": "UUID=ff55f331-…"}],
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

**`amedia space` called `command_mount` first.** `storage space` must **not** — a read-only status
command that mounts filesystems as a side effect is a surprise, and on `rue` it turns a table into a
network operation. An unmounted share renders as a row saying so; `storage mount` is one word away.

## What changes in `media`

Deletions from `src/main/resources/bin/media.sh`, all mechanical:

| Site | Change |
|---|---|
| `MEDIA_COMMANDS` (line 7) | drop `space` and `mount` |
| usage text (~81, ~84) | drop both lines |
| `command_space`, `mount_darwin`, `mount_active`, `mount_linux`, `command_mount` | delete |
| `run_stage` | drop the `space` arm |
| `main` dispatch (~962, ~970) | drop `space` from the `analyse \| refresh \| space` arm, drop `mount)` |
| `command_accepts_option` `--share` | drop `space` from the list |

`MEDIA_COMMANDS` must equal the labels `main` dispatches plus `completion`, and the unit suite
asserts that — so the assertion is the check that the deletion is complete. `mount_active` is used
only by `mount_linux`; confirm with a grep before deleting. Everything else that says `mount` in
`media.sh` (`command_move`'s cifs checks, the usbdrive `mount -t exfat` in `ingress`) is unrelated and
stays.

`MEDIA_SHARES_FILE` and `shares.csv` **stay** — losing `mount_darwin` removes one of the csv's
readers, not the file: `command_move`'s host lookup, `share_indices_all`'s completion, `deploy.sh`'s
host list and `analyse.py`'s generated remote delegation all still read it, and `media`'s own
`generate.py` still writes it from the fstab files. Leave all five alone.

**Nothing forwards.** No `amedia space` shim that calls `astorage`: the estate has one place per job,
and a forwarding command is how two copies start.

## Install and wrappers

`storage` has no `install_post.sh` today; add one on supervisor's pattern, which writes wrapper
scripts rather than symlinks so the installed path is baked and `latest` is followed:

```
/usr/local/bin/astorage    -> storage space -m local  "$@"
/usr/local/bin/astorages   -> storage space -m remote "$@"
/usr/local/bin/amount      -> storage mount           "$@"
```

`chmod +x` the binary first, as `supervisor/install_post.sh` does. On `rue` the same wrappers are
wanted; `src/rue/_macos/install.sh` is where the laptop's profile is written.

**The install path is `/var/lib/asystem/install/storage/latest/storage`** and that is what the ssh
fan-out must invoke. `deploy.sh`'s `/root/install/storage/latest/benchmark.sh` looks wrong against the
root `CLAUDE.md`'s warning about that path and is not — `/root/install` is a symlink to
`/var/lib/asystem/install` on the Linux hosts (verified on `mad`). Do not "fix" it, and do not copy
it either: the fan-out spells the real path, because `rue` has no such symlink.

## What this does not do

- **No `storage serve`**, no MQTT discovery JSON, no InfluxDB relations, no health-check fragments.
  `generate.py` keeps its single `write_schema_broker` call, which currently matches no rows.
- **No overlap with supervisor's metrics.** Supervisor already publishes `used_home_space`,
  `used_share_space`, `used_backup_space` and `failed_shares` as **percentages per host**, and those
  stay where they are. `storage` renders **per-mount detail**, which is a different question; the day
  `storage serve` exists is the day to decide whether supervisor's four rollups move, and that is a
  data migration on a published vocabulary, not a rename.
- **No `--output` column selection** (`duf` has one). The table's whole value is that every host is
  rendered identically; `--json` is the escape hatch for anything else.

## Build order

1. `go.mod` deps, `cmd.go` + `main.go` + `scribe` copied from supervisor, `storage --help` renders.
2. `internal/mount` — enumeration, classification, the identity fold, bounded statfs, unit tests over
   fixtures for all five host shapes. **This is where the plan's only real risk is.**
3. `internal/display` — the renderer, against the two committed sample files as golden output.
4. `cmd_space.go` local mode + `--json`. `astorage` is useful at this point.
5. `internal/config` + `generate.py` config.json (hosts **and** the mount map parsed out of the six
   checked-in `fstab` files); `cmd_space.go` remote mode and the ssh fan-out; the declared-but-missing
   mount row.
6. `cmd_mount.go`, then the `media.sh` deletions and the `install_post.sh` wrappers, in one change so
   the estate is never without either command.
