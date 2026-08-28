# Backup

How every stateful module is backed up, where the copies live, how long they are kept, and how to
restore. Status is marked per section: **built** is in the repo today, **planned** is not.

## Stages

**A backup run is three stages, and `stage` is the only word for one.** `hot`, `warm` and `cold` are
retired — in the prose, in the status document, in the log file names and in the Go. Each stage is
named for what it writes to, so the name and the destination can never drift:

| Stage | Writes to | Protects against | Retention | Status |
|-------|-----------|------------------|-----------|--------|
| **module** | `/home/asystem/<module>/backup/<stamp>/` | a bad release, an accidental delete, logical corruption | dense — 7 days | **built** |
| **share** | `/share/<index>0/backup/<module>/` | loss of the service data directory or its filesystem | sparse — GFS, daily 7 / weekly 4 / monthly 12 | **planned** |
| **backup** | `/backup/share/<index>0/backup/<module>/` | loss of the host or its primary share | mirror of share, `backup/` append-only | **planned** |

**The last two stages are not always available, and that is a property of the estate rather than of
the software.** The disks behind them are USB spinning drives on a switched outlet and are powered
off between runs, so the share and backup stages begin by turning that outlet on and waiting for
what fstab declares to mount. See *Powering and mounting the backup disks*.

A copy is only worth what it survives. Each stage protects against the failure the one before it
cannot, and each is thinner than the last — the retention goes from **dense** (every backup, a week
deep) to **sparse** (a year deep, a handful of points), because the further back you look the less
resolution is worth paying for.

**The share stage is not off the host.** `/share/<n>` is a local ext4 partition
(`PARTLABEL=share_08 /share/10 ext4 …`), so a host that dies takes the module and share stages with
it. The share stage exists to get copies off the service data directory and onto a large disk a
later process can pull from. Only the backup stage is a real backup.

**The backup stage is a subtree of a share replication, not a backup-specific job.** `/backup` is a
separate mounted disk that mirrors `/share`, and the stage replicates **every** mounted share on the
host — `/share/*` into `/backup/share/` — not only the primary.
`/backup/share/<index>0/backup/<module>` is simply where the module backups land inside a copy of
the *whole* share set — `media/` and `service/` come along with them. `tmp/` is excluded: it is
scratch, created by `storage/install_prep.sh` and written by things like `benchmark.sh`'s fio test
file, so replicating it costs space and preserves nothing. Two consequences, and the second is the
awkward one:

- module backups reach the backup stage **for free**, and are a rounding error beside the media on
  the same disk, which makes the sizing question in item 8 much less pressing than it looked
- **a mirror has no retention of its own**, so the sparse tail cannot live at the backup stage. It
  lives at the **share** stage instead, and the backup stage replicates the result. See
  *Retention, share stage*

`/share/<n>` mounts are numbered *host* then *drive* — mad `10 11 12`, max `20 21`, may `30 31 32`,
meg `40` — so `<index>0` is the host's primary share.

**The index is declared, not derived** — built. It is the sixth field of `.hosts`
(`mad=macmini,arm64,dar,linux,server,1`), read by `_get_host_index()` in `fabfile.py` alongside
`_get_host_arch()`, and emitted per host by `supervisor`'s generate script into the `schema` section
of `config.json`:

```json
"schema": [ { "host": "macmini-mad", "index": 1, "services": [ … ] },
            { "host": "raspbpi-jen",              "services": [ … ] } ]
```

Blank in `.hosts` for a host with no share of its own — `jen` and `jil` today — in which case the
key is omitted. Declaring it rather than deriving it from position in `.hosts` is deliberate:
inserting a host would otherwise renumber every host after it and silently file backups under
another host's share.

**A host with no index is not excluded, it borrows.** `jen` holds real state (`zigbee2mqtt`'s
coordinator database) and must reach the share and backup stages like any other host, so it mounts
another host's share and backup disk over samba rather than skipping them. The index therefore names
the *preferred* primary for a host that has one, and **fstab is the authority for a host that does
not** — the share destination is the lowest-numbered `/share/<n>` actually mounted, which on `jen`
is `mad`'s `/share/10`. That is the one place `/etc/fstab` is read rather than `config.json`, and it
is read by the mount script rather than by the plugin. See *Powering and mounting the backup disks*.

## Module contract — built

A module holding state calls `write_container_backup()` in its generate script. That produces
`src/main/resources/backup.sh`, which lands at `${SERVICE_INSTALL}/backup.sh` on the host, runs
there, and writes into the module's own backup root. **That script is the module stage and nothing
else** — it knows nothing of `/share`, `/backup`, the schedule, the status document or the metrics.

**The call is the enrolment.** No call, no generated script, no participation — exactly as a module
without `write_container_healthchecks()` has no health checks. There is no `<MODULE>_BACKUP_ENABLED`
variable, because the presence of the call already says it. No registry, no list, and no way to be
half-enrolled, since the declaration is what produces the backup.

```python
write_container_backup()    # the whole enrolment, no policy parameters
```

**`supervisor` does not call it, and must not.** Supervisor is the driver, not a participant in the
mechanism it drives, and a `backup.sh` of its own would be a second implementation of the run it is
already performing in Go. Its own state is copied by the **supervisor module backup** described
under *Driver*, which is a step of the module stage rather than a generated script. Six modules are
enrolled today — `postgres`, `mariadb`, `influxdb3`, `zigbee2mqtt`, `letsencrypt`, `plex`.

**The call takes no policy.** It resolves `module_name` / `working_dir` the standard way and nothing
else — the two policy values are wrapper variables with defaults, `BACKUP_RETAIN_DAYS` (7) and
`BACKUP_SKIP_HOURS` (1), each written as `${VAR:-default}` **after** the module's `.env` is
sourced. So a module changes them in its env files, and an operator overrides them per run:

```bash
BACKUP_SKIP_HOURS=0 ./backup.sh    # take one now, whatever the last run's age
```

A generate parameter could do neither of those, which is why they are variables.

### Backup naming

```
<data root>/backup/<stamp>/<module>_<stamp>_<version>_full.<extension>
<data root>/backup/<stamp>/<module>_<stamp>_<version>_delta.<extension>
```

`<data root>` is the **parent** of the data directory, so backups sit beside the versioned homes
rather than inside one — `/home/asystem/<module>/backup`, not `/home/asystem/<module>/<version>/backup`.
That keeps them clear of `install.sh`, which copies the old home into the new one on every deploy and
prunes the older homes; a backup directory inside a home was duplicated forward by that copy.

`<stamp>` is `%Y-%m-%d_%H-%M-%S` local, in both the directory and the filename. The directory name is
the bare stamp and nothing else — `backup_listed` matches it with an anchored pattern, so anything
appended there would hide the backup from listing, pruning and the health check.

`<version>` is the version the backup was **extracted from** — the basename of the resolved
`BACKUP_SOURCE_PATH`, not `SERVICE_VERSION_ABSOLUTE`. The two differ exactly when it matters: on an
upgrade the wrapper runs from the new install directory, whose `.env` names the version being
deployed, while the data being backed up is the old home. It sits before the suffix so `_full` /
`_delta` stay immediately before the extension. The **`_full` / `_delta` suffix is the whole
point**: it tells a later stage, without knowing anything about the module, whether a backup stands
alone.

- **`_full`** is self-contained. It can be kept as a sparse restore point and deleted individually.
- **`_delta`** depends on the full before it. It is only meaningful inside a window that also holds
  that full, and deleting a full invalidates every delta after it.

That is what makes GFS possible at the share stage without the driver learning anything
module-specific: monthly and weekly points must be `_full`, and `_delta` backups are only retained
inside the dense window. Modules producing standalone backups always emit `_full`; only `influxdb3`
emits both.

### Kinds

Two kinds, named for what a single backup is worth on its own:

| Kind | Meaning |
|------|---------|
| `FULL` | self-contained backups only, each one restorable on its own |
| `DELTA` | dependent backups, a `_full` and the `_delta`s hanging off it |

| Module | Kind | Produced by | Backup |
|--------|------|-------------|----------|
| `postgres` | `FULL` | `pg_dumpall \| gzip` in the container | `postgres_<stamp>_<version>_full.sql.gz` |
| `mariadb` | `FULL` | `mariadb-dump --all-databases --single-transaction \| gzip` | `mariadb_<stamp>_<version>_full.sql.gz` |
| `zigbee2mqtt` | `FULL` | `zigbee/bridge/request/backup`, base64 zip off the response topic | `zigbee2mqtt_<stamp>_<version>_full.zip` |
| `letsencrypt` | `FULL` | `backup_files`, the shared `tar` of the paths it is passed | `letsencrypt_<stamp>_<version>_full.tar.gz` |
| `plex` | `FULL` | `backup_files` with the service stopped | `plex_<stamp>_<version>_full.tar.gz` |
| `influxdb3` | `DELTA` | `influxdb3 create backup`, tarred out of the object store | `influxdb3_<stamp>_<version>_{full,delta}.tar.gz` |

A `FULL` backup is always self-contained, so any subset can be kept. A `DELTA` module emits a `full`
when there is none or the current one has aged past `BACKUP_RETAIN_DAYS`, and a `delta` against the
newest member otherwise.

### What the snippet gets

The wrapper defines the variables and functions below, then inserts the module's snippet, so a
snippet **overrides simply by redefining** — no hook protocol, no registration. **The prefix says
which side of the line a name is on**, and the rule is one-directional: a snippet never assigns a
wrapper variable, and the wrapper never reads a snippet one.

| Namespace | Owner | Rule |
|-----------|-------|------|
| `BACKUP_*` | wrapper | published for the snippet to read, never assigned by a snippet |
| `BACKUP_INTERNAL_*` | wrapper | its own — the throttle, the exit status, the `.env` path |
| `<MODULE>_*` | snippet | a snippet's own state, prefixed with its module so it cannot collide with either |

| Variable | Meaning |
|----------|---------|
| `BACKUP_MODULE_NAME` | the module name |
| `BACKUP_SOURCE_PATH` | `${SERVICE_DATA_DIR}`, the module's data directory |
| `BACKUP_SOURCE_VERSION` | the version the backup was extracted from, the resolved source path's basename |
| `BACKUP_INTERNAL_ROOT_DIR` | `$(dirname "${BACKUP_SOURCE_PATH}")/backup`, beside the versioned homes rather than inside one |
| `BACKUP_RUN_TIMESTAMP` | this run's timestamp |
| `BACKUP_FULL_SUFFIX` / `BACKUP_DELTA_SUFFIX` | the `_full` / `_delta` suffixes |
| `BACKUP_RETAIN_DAYS` | the dense window in days, default 7 |
| `BACKUP_SKIP_HOURS` | skip the run when the newest backup is younger than this, default 1 |
| `BACKUP_SERVICE_RESTART` | start the service again after the copy, false when the caller starts it itself |
| `BACKUP_TARGET_PATH` | the backup path — empty until `backup_target` names it |

| Function | Purpose |
|----------|---------|
| `backup_target <suffix> <extension>` | name this run's backup, set `BACKUP_TARGET_PATH`, create its directory |
| `backup_epoch <name>` | timestamp to epoch |
| `backup_listed [dir]` | the stamp directories, oldest first |
| `backup_versioned <name>` | the version a backup directory was extracted from |
| `backup_healthy [dir]` | the newest backup is younger than a day plus an hour's allowance |
| `backup_pruned [dir]` | delete past `BACKUP_RETAIN_DAYS`, always keeping the newest |
| `backup_is_full` / `backup_is_delta` | classify a backup by its suffix |
| `backup_included` / `backup_unmatched` | resolve the passed paths, report what they do not cover |
| `backup_files <paths> [extension]` | the shared file copy — names a `_full` backup, then `tar`s the colon-separated paths into it |
| `backup_written` | writes the backup — **every snippet defines this**, the wrapper's only fails |

**There is no `BACKUP_EXTENSION`, and no snippet assigns `BACKUP_TARGET_PATH`.** Both were snippet →
wrapper writes: the snippet set a global that code *below* it read to compose the path, which is why
`influxdb3` had to reassign `BACKUP_TARGET` twice and `mkdir` the parent itself — only the produce
write step knows whether a run is a full or a delta. Naming is now a call inside `backup_written`, so the
suffix and the extension are arguments at the point of use and the wrapper computes nothing it
cannot know:

```bash
backup_written() {
  backup_target "${BACKUP_FULL_SUFFIX}" "sql.gz" || return 1
  docker exec --user root "${BACKUP_MODULE_NAME}" \
    bash -c 'pg_dumpall -U postgres | gzip' >"${BACKUP_TARGET_PATH}.tmp"
}
```

**Every snippet defines `backup_written`, including a plain file copy.** The wrapper's own
definition does nothing but fail with a reason, so a module that forgets it is a loud failure rather
than a silent one, and reading a snippet always tells you how that module is produced. `letsencrypt`
defers to the shared file copy, which names the backup for it:

```bash
backup_written() {
  backup_files "letsencrypt/accounts:letsencrypt/archive:letsencrypt/live:letsencrypt/renewal"
}
```

A run where `backup_written` never named a backup is reported as such and fails, rather than
renaming a file nothing wrote.

**A snippet reads `.env` values with `"${VAR:?}"`.** `mariadb` needs `MARIADB_ROOT_PASSWORD` and
`zigbee2mqtt` needs `VERNEMQ_SERVICE`/`VERNEMQ_API_PORT`; expanded bare, a renamed or missing key
becomes an empty argument and the failure surfaces as a confusing tool error, or worse as a
truncated backup. The `:?` form fails by name at the point of use.

`influxdb3` defines `backup_written`, adds its own full/delta helpers, and keeps its state in
`INFLUXDB3_BACKUP_CLUSTER` / `INFLUXDB3_BACKUP_STORE`, the directory the server writes its own
backups into — which is what `backup_stored` lists, as distinct from the wrapper's `backup_listed`
over our backups.

**It waits, and that is not removable.** `influxdb3 create backup` returns as soon as the server has
accepted the job, so `backup_awaited` polls `influxdb3 status backup` until `completed` — without it
the `tar` captures an in-flight backup directory and writes a valid gzip holding partial data, the
one failure this design cannot detect later. What *was* removed is everything around the wait:
progress lines every 30 seconds, a `TIMEOUT` knob and a cancel-on-timeout, none of which change the
backup. The same `backup_status` also answers the full-versus-delta question, since a parent must
be `completed` before a delta can be taken against it.

### It is sourceable, and that is how the share stage avoids knowing anything

The generated script ends its definitions with:

```bash
[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0
```

Executed, it takes a backup. **Sourced, it defines the module's vocabulary and returns**, so the
share stage can source a module's own `backup.sh` and get `BACKUP_FULL_SUFFIX`,
`BACKUP_DELTA_SUFFIX`, `backup_is_full`, `backup_listed`, `backup_pruned` and the rest — for *that*
module — without supervisor containing a single module-specific line. The share stage decides the
policy; the module supplies the vocabulary and the thinning.

Source each module in a subshell: the wrapper sources the module's `.env`, and six modules' worth
of environment in one shell would collide.

`backup.sh --prune <dir>` remains for the same job as a subprocess, where sourcing is not wanted.

### Safety is the module's, not the driver's

Each module's script owns what is safe to copy and how. The driver never inspects a data directory,
never decides what to exclude, and never knows a backup format.

**Back up what git cannot restore.** Most of a file module's tree is shipped from
`src/main/resources/data/` and re-copied over the live directory by `install.sh` on every release —
HA's `configuration.yaml`, `automations.yaml`, `custom_components/`, `ui-lovelace/`, `www/`; z2m's
`configuration.yaml`, `devices.yaml`, `groups.yaml`. Backing those up produces a worse copy of the
repository. What matters is the state the application generates: HA's `.storage/` (auth, entity and
device registries, everything UI-managed), z2m's `database.db` and coordinator backup.

That criterion is why `backup_files` takes an allow-list rather than a deny-list. The set of things worth
keeping is small and stable; the set of junk is open-ended and grows with every upstream release.

**An allow-list fails toward too little, which is the one thing to guard.** Bloat is visible and
recoverable; a silently omitted directory is neither. So a file-copying script **must record the
top-level entries no include pattern matched** in its result, so a newly appeared state directory
surfaces as unbacked rather than being discovered at restore. With that reporting, an allow-list is
strictly better than a deny-list — a small deliberate backup *and* drift notification.

Rules for a file-copying module:

- the `backup/` output directory is **always** excluded, implicitly — never left to a pattern.
  Both file modules mount their whole data directory (`${SERVICE_DATA_DIR}:/config` for HA,
  `:/app/data` for z2m), so the output sits inside the tree being copied and a missed exclusion
  nests exponentially, silently, until the disk fills
- an empty path list is a loud skip with a reason, never a silent success
- preserve ownership, permissions, xattrs and symlinks, and never dereference — a copy that loses
  them restores looking complete and will not start
- write to a temporary name and rename on success, so the share stage never copies a half-written
  backup

**Prefer the application's own mechanism over a file copy**, in this order:

1. the application's backup API — HA's backup integration, z2m's
   `zigbee2mqtt/bridge/request/backup`, `pg_dumpall`. Both file modules already hold the
   credentials they need. A module with a native mechanism ignores `backup_files` and `OFFLINE` entirely
2. quiesce — `OFFLINE=true`, stop, copy, start; only where the downtime is acceptable
3. copy of files the application guarantees atomic or append-only
4. a naive copy of a live tree — **not acceptable** for anything containing a database

A filesystem snapshot is a better `OFFLINE` implementation than stop-copy-start on these hosts,
which run btrfs and LVM: atomic, near-instant, no downtime. Copy from the snapshot, then drop it.

`EXCLUDE` is deliberately absent. `backup_files` cannot express "this directory but not that
subdirectory"; add subtraction if and when a module needs it, applied after the allow-list, not before.

### Copy safety

All backups can be copied while the service runs and while a backup is in progress.

- SQL dumps stream to `<file>.tmp` and are renamed only once `set -o pipefail` confirms success, so
  a reader never sees a partial `.gz` and a failed dump never overwrites a good one. Stale `.tmp`
  files from a crashed run are swept on the next run.
- influxdb3's `backup/` is a hardlinked mirror of `cluster_1/backups`, added to per backup via
  `.partial` plus an atomic rename and never rebuilt wholesale, so paths are stable, an incremental
  `rsync` transfers only what changed, and it costs no disk.

### Retention, module stage

`BACKUP_RETAIN_DAYS` is a guaranteed **minimum** recoverable window, not a footprint.

`FULL` modules delete backups older than the window, always keeping the newest whatever its age, so
a run of failures can never leave zero backups.

influxdb3 cannot be thinned that way. Restoring a delta walks back to the full it hangs off, and
deleting any backup cascades to everything depending on it, so the unit of retention is a full and
all its deltas. Two rules, same knob:

- **start a new full** when the current one is older than the window
- **delete a full and its deltas** only once the *next* full is older than the window, which is
  what keeps the window covered by a full predating it

A 7 day window therefore retains around 12 days and two fulls. Correct, not waste.

## Adding a backup script

1. **Decide the verdict.** Back up what git cannot restore. If everything in the data directory is
   redeployed from `src/main/resources/data/` or lives in a database that is itself backed up, the
   module is *derived* and needs nothing — record that in the inventory rather than leaving it blank.
2. **Write the snippet** at `src/build/resources/backup.sh`. Define `backup_written` — either
   passing the paths to copy to `backup_files`, or naming the backup with `backup_target` and
   writing `"${BACKUP_TARGET_PATH}.tmp"` itself. Prefer the application's own backup mechanism over a file copy; where
   producing the backup needs something only inside the container, wrap that one command in
   `docker exec` and redirect host-side.
3. **Call `write_container_backup()`** in the module's generate script. That call is the entire
   enrolment — there is no parameter, no registry, and omitting it is how a module opts out. Set
   `BACKUP_RETAIN_DAYS` / `BACKUP_SKIP_HOURS` in the module's env files if the defaults are
   wrong for it.
4. **Run `fab generate`.** It writes `src/main/resources/backup.sh` with the build banner and
   the executable bit. Never edit that file; edit the snippet.
5. **Wire nothing.** The driver finds the module by the generated script existing at
   `${SERVICE_INSTALL}/backup.sh` — which `probe_install.go` already records as
   `installService.backupEnabled`. Do not add an `install_pre.sh` or `install_prep.sh`; per-module
   release hooks are retired and `install.sh`'s own `run_backup` covers the release-time call for
   every module at once.
6. **Do not add it to `src/resources.txt`.** The script reads its environment at runtime and holds
   no `${VAR}` placeholders.
7. **Check the result**: a successful run leaves exactly one backup named
   `<module>_<stamp>_<version>_full.<extension>`; a failed one leaves no file and no directory. Running it
   twice inside `BACKUP_SKIP_HOURS` must skip. Sourcing it must produce no backup.

## Driver — planned

**`supervisor` runs the schedule, in Go, from its own container.** There are exactly two invokers of
a module's `backup.sh` and they answer different questions:

| Invoker | When | Why |
|---|---|---|
| `install.sh`'s `run_backup` | at release, before the old home is replaced | a safety copy of the version being upgraded away from — built |
| `supervisor`'s backup plugin | daily, at `--daily-time` | the estate's actual backup cadence — planned |

Per-module release hooks are gone: `run_backup` sits in the **root** `install.sh`, selects on
`${SERVICE_INSTALL}/backup.sh` existing, runs only for `COMMAND=install` with
`BACKUP_SKIP_HOURS=24 BACKUP_SERVICE_RESTART=false` under `timeout 1800`, and aborts the install if
the backup fails. That is one call site for every module and needs nothing from this plan.

**Supervisor has no `backup.sh` of its own.** The whole driver is
`internal/plugin/plugin_backup.go`, which is the single new Go file — no `write_container_backup()`
call in `supervisor/generate.py`, no `src/build/resources/backup.sh` snippet, no supervisor entry in
the enrolled-module set. It does ship **one** script of its own, `mount.sh`, and the distinction is
worth stating precisely: `mount.sh` is not a backup, does not participate in the module stage and is
not produced by the backup generator — it makes the estate's disks *available*, which is a
host-and-fstab job that shell does natively and Go would only wrap. Nothing about producing,
naming, promoting or thinning a backup is expressed in shell by supervisor. The
previous design put the driver in supervisor's own generated script and let Go schedule it; that
inverted the responsibilities, because everything the driver does — discovering modules, ordering
stages, timing them, writing a machine-readable result, judging staleness, feeding three metrics —
is already what the Go process does for every other subject on the host, and none of it is
module-specific shell.

### The daily gate

**`--daily-time` is a new `serve` flag, defaulting to `01:00`**, and it is generic infrastructure
rather than a backup flag. The pulse loop already distinguishes a poll from a pulse from a
heartbeat; the gate adds one more classification on the same tick:

```
supervisor serve --daily-time 01:00        # -D, HH:MM local, the same clock the stamps use
```

- `config.DefaultDailyTime` is `"01:00"`, spelled once, and `cmd_serve.go` gives the flag its
  default from that constant — the same shape as `DefaultPollPeriod` and `DefaultPulseFactor`.
- `makePeriods` parses it into `config.Periods.DailyMinutes`, minutes past local midnight, so the
  flag joins the existing period vocabulary rather than inventing a second one. An unparseable value
  is a startup error, like a bad `--log-action`.
- `probe.Run` computes the crossing on each **pulse** and passes it down beside the heartbeat flag:
  `onPulse(isHeartbeat, isDaily)`. `isDaily` is true on the first pulse whose local wall clock is at
  or past the configured minute of a day on which the gate has not yet fired, so it fires **at most
  once per calendar day** and never twice in the window.
- **The crossing is a wall-clock question, so it uses `config.NowIncludingSuspend()`.** A monotonic
  reading would miss the crossing entirely across a suspend, and this is exactly the split the
  *Clocks* section of `CLAUDE.md` records: "how long have I waited" is monotonic, "what time is it"
  is wall.
- A host that is down at `01:00` has missed that day. The gate does **not** catch up on start —
  a supervisor restarted at 09:00 does not immediately fire yesterday's run, because the staleness
  rule below already reports the gap and a backup storm on every restart is worse than a late one.
- The gate logs one line when it fires and nothing when it does not, so a quiet day costs nothing.

**Anything else wanting a daily cadence hangs off the same flag.** The gate is a boolean on the
pulse, not a backup callback, so a future daily task is one more consumer of `isDaily` rather than a
second scheduler. That is the reason it lives in `probe.Run` beside the heartbeat rather than inside
the backup plugin.

### What the plugin does when the gate fires

Inputs come from `config.json`, already loaded, already carrying everything needed — there is no
second config file and no `/etc/fstab` discovery:

- `.asystem.host` → this host and, via `.asystem.schema[]`, its share `index`
- `.asystem.schema[] | select(.host == $host) | .services[]` → the modules configured for this host

Participation is `installService.backupEnabled` from `probe_install.go`, which already `Lstat`s
`<install>/<service>/latest/backup.sh` on every snapshot — so the plugin reuses the install snapshot
rather than walking the tree itself, and a module enrolling or leaving is picked up by the existing
stat fingerprint with nothing new to invalidate.

The three stages run **serially, in order**, because each depends on the one before: the share stage
has nothing to copy until the module stage has produced it, and the backup stage nothing to mirror
until the share stage has been written and thinned.

**module** — for each module configured on this host, **serially**, skipping any with no
`backup.sh` and any whose container is not running:

1. **The supervisor module backup runs first**, before any other module. It `tar`s supervisor's
   **state** directory — every past run's `status.json` and `logs/` — into
   `supervisor_<stamp>_<version>_full.tar.gz` under this run's stamp directory in the standard
   backup root, so the record of past runs is carried into the share and backup stages with
   everything else. **The source and the destination are two different directories**, which is what
   makes this an ordinary backup rather than a directory copying itself: it reads `state/backup/`
   and writes `backup/`. **This run's own `status.json` and its share and backup stage logs are
   deliberately not in it**: they do not exist yet, and waiting for them would mean either running
   the supervisor backup last, after the stages it is meant to precede, or writing the status
   document twice. The accepted consequence is that the newest run's own record only reaches the
   share stage on the following day.
2. execute `${SERVICE_INSTALL}/backup.sh` with no arguments and no environment — it sources its own
   `.env`
3. exit `0` is produced or throttled by its own `BACKUP_SKIP_HOURS`, non-zero is failed; the rest of
   its output is that module's log
4. it writes `/home/asystem/<module>/backup/<stamp>/<module>_<stamp>_<version>_{full,delta}.<ext>`
5. never read a data directory, choose an exclusion or parse a backup — the module owns its format,
   its throttle and its pruning

**share** — **`mount.sh up` first**, powering the outlet and mounting what fstab declares; if it
fails, the share and backup stages are both recorded failed and nothing is copied. Then, for each
module whose module stage succeeded, so a bad backup is never promoted:

1. `rsync -a --link-dest` of the previous copy, no `--delete`, of `/home/asystem/<module>/backup/`
   into `/share/<index>0/backup/<module>/`, with `--temp-dir` (see *Surviving a hard reset*)
2. source that module's `backup.sh` in a subshell, so `backup_is_full`, `backup_is_delta` and
   `backup_listed` are its own, or call `backup.sh --prune <dir>` as a subprocess
3. thin to grandfather-father-son, oldest tier wins a tie:
   - **son** — every backup of either kind inside `BACKUP_RETAIN_DAYS`
   - **father** — the newest `_full` of each ISO week, for `BACKUP_KEEP_WEEKLY` weeks
   - **grandfather** — the first `_full` of each month, for `BACKUP_KEEP_MONTHLY` months
4. a `_full` stands alone, a `_delta` restores only with its `_full` and every `_delta` between, so
   father and grandfather are always `_full`, only son may hold a `_delta`, and a `_delta` whose
   `_full` has gone is dropped

**backup** — once, after the share stage, for each mounted share on this host rather than only the
primary, both sides guarded on `mountpoint`:

1. `rsync -a --delete --exclude backup/ --exclude tmp/` of `/share/<n>/` into `/backup/share/<n>/`,
   `tmp` being scratch never worth replicating
2. `rsync -a`, no `--delete`, of `/share/<n>/backup/` into `/backup/share/<n>/backup/`, so a
   mistaken thin at the share stage cannot reach the backup copy

Both carry `--temp-dir` for the same reason as the share stage.

**Guard on `mountpoint` before every write**, even though `mount.sh up` has already asserted it —
the mount can lapse in between, and writing to an unmounted `/share/10` silently creates the path on
the root filesystem and fills the OS disk rather than merely failing.

Then `mount.sh down` to unmount, `done/<host>` to report, and — on the leader alone — the destroy
that switches the outlet off.

### Powering and mounting the backup disks

**The disks are on a switched outlet and are unmounted between runs.** `rack_backup_plug` — a Sonoff
BasicR2 in the rack, already declared in `src/meg/tasmota/src/build/resources/devices/` and already a
Home Assistant switch entity — powers **every** USB backup drive in the estate at once. Nothing is
mounted until it has been on long enough for the drives to spin up and enumerate, so the share and
backup stages cannot simply `rsync` into a path and hope.

**`mount.sh` owns this, and it is the only script supervisor ships that the build does not
generate.** Everything else under `src/main/resources/image/` is written by `fab generate` — the
three health checks from their fragments, `broker.sh`, `config.json` — whereas this is hand-authored
at `src/main/resources/image/mount.sh` and edited in place. There is no `write_container_mount()`
and there should not be: generation exists to remove repetition between modules, and exactly one
module has this problem.
It takes a phase, in the shape `broker.sh [sweep|publish]` already established:

```
/asystem/etc/mount.sh up      # switch on, wait for readiness, mount what fstab declares
/asystem/etc/mount.sh down    # unmount what it mounted, leaving the outlet alone
```

**`up` does four things, in order, and each is idempotent:**

1. **Switch on.** Publish `ON` to `tasmota/device/rack_backup_plug/cmnd/POWER` and wait for the
   retained `tasmota/device/rack_backup_plug/stat/POWER` to read back `ON`, bounded by a timeout.
   `mosquitto-clients` is already in `docker_deps_base.txt` and `BROKER_HOST`/`BROKER_PORT` are
   already in the container's environment, so this needs no new dependency. A plug already on
   answers immediately and costs one round trip. **Never publish to the device's `stat` topic** —
   that is the device's to write, and faking it is the same error as publishing
   `homeassistant/status` on Home Assistant's behalf.
2. **Wait for readiness.** A spinning disk is not ready when the relay closes. The script waits for
   the devices behind the fstab entries to appear, bounded by `mountReadySeconds`, polling rather
   than sleeping a fixed period — so a run finding the disks already spun up costs milliseconds and
   one finding them powered down still waits as long as it has to.
3. **Mount what fstab declares, and only that.** The script never invents a mount: it reads
   `/etc/fstab`, selects the entries it is responsible for, and `mount`s each by mountpoint. **The
   fstab entry is the declaration and the script is the enactment**, which is the same division
   `storage/install_prep.sh` already uses when it reads `/etc/fstab` for `/share` `ext4` lines to
   decide which shares to publish over samba.
4. **Assert.** Every mountpoint it was responsible for is `mountpoint`-clean, or `up` fails with the
   list of those that are not.

**It decides local versus remote from the fstab line, never from the host name.** A `/backup` line
of a local filesystem type is a directly attached disk; a `cifs` line is another host's disk over
samba, and needs its credentials and its network rather than a spin-up wait. So the same script
covers both without a per-host branch:

| Host | `/share/<n>` | `/backup` |
|---|---|---|
| `mad`, `max`, `may`, `meg` | local, its own numbered shares | local, its own USB backup disk |
| `jen` | `cifs` from `mad`, mounted at `/share/10` | `cifs` from `mad` |

**`jen`'s two mounts are not symmetrical, and only one of them is the script's problem.**
`/share/10` is mounted **automatically by fstab** and needs nothing from `mount.sh` beyond the
readiness assertion — the drive behind it on `mad` still has to be powered and spun up first, which
is the whole reason step 1 is estate-wide rather than per host. `/backup` is the on-demand one: its
fstab entry is `noauto`, and `mount.sh` mounts and unmounts it around the run.

**Switching on and switching off are not the same problem, and `mount.sh` only solves the first.**
One plug powers every host's drive, so switching **on** is idempotent and safe from anywhere, while
switching **off** would cut another host mid-`rsync` — including `jen`, writing to `mad`'s disk over
samba. So `mount.sh up` switches on, `mount.sh down` unmounts and leaves the outlet alone, and the
outlet is switched off by exactly one host per day, elected. See *The cluster singleton*.

`rack_backup_plug` publishes no energy entity today, so nothing reports what an outlet left on
costs. Adding one — the shape `rack_outlet_plug` and `ceiling_network_switch_plug` already use — is
what would turn "wasteful" from a judgement into a number.

**A Tasmota warm restart leaves the relay alone**, so `tasmota`'s `broker.sh` recovery fragment
restarting its devices cannot power the disks down mid-run — but note `rack_backup_plug` is an
ESP8285, where that guarantee holds; the ESP32 caveat in the root `CLAUDE.md` does not apply here.
Its `PowerOnState` should nonetheless be confirmed, since a cold power-up of the plug itself decides
whether the disks come back after a rack outage.

**Failure is a recorded stage failure, never a partial copy.** If the switch does not answer, a
device does not appear, or a mount does not assert, `up` exits non-zero, the share and backup stages
are marked `success_bool: false` with the reason in `logs/share.log`, and the module stage's result
stands on its own — the day's backups still exist locally and are promoted on the next successful
run, because the copy from the module stage is additive and no data is lost by a skipped promotion.

### The cluster singleton

**One host per day powers the outlet on and off; every other host waits for it and reports back.**
The election runs on the broker every host is already connected to, using only retained messages and
a last will — no new dependency, no new service, and nothing that survives a broker recreate, which
is correct because a broker recreate should void a lease rather than preserve it.

Four retained topics under one namespace, all QoS 1:

| Topic | Payload | Written by | Cleared by |
|---|---|---|---|
| `supervisor/backup/leader` | `{"host":…,"epoch":…,"expires":…}` | a candidate claiming the lease | the leader when done, or its last will |
| `supervisor/backup/power` | `<ready\|off>` | the leader, after `mount.sh up` succeeds | the leader when done |
| `supervisor/backup/done/<host>` | the run's stamp | each host as it finishes its stages | the leader when done |
| `supervisor/<host>/status` | `<online\|offline>` | **already exists** — each `serve` | its own last will |

**Election is publish, settle, confirm — and it is a mutex, not a consensus protocol.** The broker
serialises writes to one retained topic, so the last write wins and every reader converges on the
same value. That is all this needs:

1. Only `mad`, `max`, `may` and `meg` are candidates, in that order — they hold the disks. `jen` and
   any future host with no local share never claims, it only waits.
2. A candidate publishes `{host, epoch, expires}` retained to `supervisor/backup/leader`, with its
   **last will set to an empty payload on that same topic**, so a crash clears the lease rather than
   stranding it.
3. It waits `leaderSettle` and reads the topic back. Its own value means it leads; anyone else's
   means it follows. Two hosts publishing at once both read the same final value, so exactly one
   leads and the other yields without a negotiation round.
4. A candidate finding a lease that is **already held and not expired** follows immediately and does
   not publish. One finding an **expired** lease claims it, which is what recovers a leader lost to
   a hard reset before its will was delivered.
5. If no lease can be established within `leaderTimeout`, the host **runs its module stage anyway**
   and records the share and backup stages failed with the reason. A failed election must never cost
   a local backup.

**The lease is the timeout, and it is `backupRunCeiling` — five hours.** That one constant on
`plugin_backup.go` does three jobs, which is why it is one constant and not three: it bounds the
leader's hold, it is the ceiling on a whole run, and it is the allowance in the staleness window
(`backupStaleWindow` = 24 h + `backupRunCeiling` = **29 hours**). A run that has not finished in
five hours is not going to, and holding the outlet on past that is worse than cutting it.

**The leader's init and destroy are the singleton, and nothing else is.** Everything between them is
ordinary per-host work happening in parallel:

- **init** — `mount.sh up`, then publish `power=ready`. Only the leader ever switches on.
- **destroy** — publish `power=off`, `mount.sh` power-off, then clear `leader`, `power` and every
  `done/<host>`. Reached when every expected host has reported `done`, or when the lease expires,
  whichever is first.
- **the expected set is read, not configured** — every host whose retained `supervisor/<host>/status`
  is `online` and which is configured to back up. So a host that is down does not hold the outlet on
  for five hours, and no list has to be maintained anywhere.

**A follower waits for `power=ready`, bounded by `leaderTimeout`**, then mounts and runs its share
and backup stages, then publishes `done/<host>`. It never touches the switch. The leader is an
ordinary host in every other respect — it runs the same three stages as everyone else, and its own
`done` counts like any other.

**The module stage is outside all of this.** It writes only to `/home/asystem`, needs no powered
disk and no mount, so it runs immediately at `--daily-time` on every host with no election, no
waiting and no dependency on the broker. Only the share and backup stages are wrapped. That is worth
being explicit about, because it means **a total failure of the election still produces the day's
backups** — it only costs their promotion.

### Surviving a hard reset

**A copy interrupted by a power cut must leave no half-written file, and the next run must redo it
whole.** These are USB disks on a switched outlet, so an interrupted copy is a routine event rather
than an exceptional one, and it has to be designed for rather than recovered from.

**Never `--partial`, never `--inplace`, always `--temp-dir`.** rsync's default is already to write a
temporary file and rename it into place, so a destination file is either the previous complete
version or the new complete one and never a blend — `--inplace` would destroy that property and
`--partial` would deliberately keep the fragment. What the default does *not* do is clean up after a
kill: the temporary is left wherever it was being written, scattered through the destination tree
under dotted names. So every `rsync` here passes `--temp-dir=<dest>/.rsync`, which puts every
partial in one known directory on the destination filesystem — keeping the rename atomic — and the
stage **wipes that directory before it starts**. A reset therefore costs the transfer of one file,
redone in full on the next run, and leaves nothing behind that a later run could mistake for data.

**Everything else is already idempotent, so a re-run is a resume.** The copies are additive, the
module backups are `.tmp`-and-renamed by their own wrapper, and `status.json` is written last — so a
run killed part way leaves no status document, the day reads as failed, and the next run copies
what the interrupted one did not. Nothing needs a journal, a resume marker or a lock file surviving
the reset.

**A reset also strands the lease and the outlet**, and both are covered: the leader's last will
clears `supervisor/backup/leader` if the broker notices, and the `expires` stamp lets the next day's
candidate claim it if the broker does not. The outlet stays on in the meantime, which is the safe
direction to fail.

### The run's output

**Supervisor's data directory holds two backup trees, and confusing them is the one mistake to
avoid.** One is the run's record, which the driver *writes*; the other is the standard backup root,
which supervisor's own module-stage backup *produces* like any other module's. Both sit under the
one existing `${SERVICE_DATA_DIR}:/asystem/mnt` volume, so the plugin writes container paths and
needs no prefix awareness:

| Tree | Container | Host | Holds | Written by |
|---|---|---|---|---|
| **state** | `/asystem/mnt/state/backup/` | `/home/asystem/supervisor/latest/state/backup/` | one directory per run — `status.json` and `logs/` | the driver, every run |
| **backup** | `/asystem/mnt/backup/` | `/home/asystem/supervisor/latest/backup/` | `supervisor_<stamp>_<version>_full.tar.gz` of the state tree | the supervisor module backup, first step of the module stage |

The **state** tree is the driver's own working record and is not itself a backup — it is the thing
being backed up. The **backup** tree is the standard place, named and stamped exactly as every other
module's is, which is what lets the share stage promote it without a special case. Reading them the
other way round — the driver writing into `backup/` — would have the supervisor backup tar the
directory it is writing into, which is the nesting hazard the module contract already warns about
for file-copying modules.

The state layout is fixed and is the contract every reader depends on:

```
/asystem/mnt/state/backup/<stamp>/
├── status.json                     the machine-readable result, written once, last
└── logs/
    ├── module.log                  the module stage's own log
    ├── share.log                   the share stage's own log
    ├── backup.log                  the backup stage's own log
    └── module/
        ├── postgres.log            one file per module run in the module stage
        └── influxdb3.log           stdout and stderr of that module's backup.sh
```

`<stamp>` is `%Y-%m-%d_%H-%M-%S` local — the same format the module backups use, so a run directory
and the module backup directories it produced sort together and read the same way. There is one
`logs/module/<module>.log` per module actually executed, so a module that was skipped for having no
script contributes no file.

**Both trees sit inside the versioned home, which is deliberate and has one consequence.** Every
other module's backup root is `/home/asystem/<module>/backup`, a sibling of the versioned homes, so
that `install.sh`'s `cp -rfpa` of the old home into the new one does not duplicate it. Supervisor's
are inside `latest/` instead, so **a release copies both trees forward** — which is what keeps the
run history across a deploy, and is bounded by `retire_home` pruning the older homes and by
`BACKUP_RETAIN_DAYS` pruning the tars. Watch the cost: supervisor releases often, and `state/backup`
grows by one directory a day per host.

**`status.json` is written once, at the end of the run, and never updated in place.** A partially
written status document is indistinguishable from a completed run that failed, which is precisely
the ambiguity the staleness rule below has to resolve. It is written to `status.json.tmp` and
renamed, so a reader never sees a partial one.

The document is one shape repeated at three levels — the run, each stage, and each module within the
module stage — so a reader learns one set of keys and applies it everywhere:

```json
{
  "started_ts": "<portable timestamp>",
  "finished_ts": "<portable timestamp>",
  "duration_s": "<number>",
  "success_bool": "<true|false>",
  "disk_usage_perc": "<number>",
  "file_count": "<number>",
  "size_mb": "<number>",
  "stage": {
    "module": {
      "started_ts": "<portable timestamp>",
      "finished_ts": "<portable timestamp>",
      "duration_s": "<number>",
      "success_bool": "<true|false>",
      "disk_usage_perc": "<number>",
      "file_count": "<number>",
      "size_mb": "<number>",
      "module": {
        "postgres": {
          "started_ts": "<portable timestamp>",
          "finished_ts": "<portable timestamp>",
          "duration_s": "<number>",
          "success_bool": "<true|false>",
          "disk_usage_perc": "<number>",
          "file_count": "<number>",
          "size_mb": "<number>"
        },
        "influxdb3": { "…": "…" }
      }
    },
    "share":  { "…": "…" },
    "backup": { "…": "…" }
  }
}
```

| Key | Meaning at every level |
|---|---|
| `started_ts` / `finished_ts` | RFC 3339 local with offset, so a stamp is portable and comparable without knowing the host's zone |
| `duration_s` | wall seconds, `finished_ts - started_ts` |
| `success_bool` | this level completed without a failure; a stage is true only when every module under it is true |
| `disk_usage_perc` | percentage used of the filesystem this level **wrote to** — the module data volume, `/share`, `/backup`. At the run level it is **`/backup` alone**, not a roll-up of the three, because that is the volume `Used BKP` names |
| `file_count` | files this level wrote or holds at its destination |
| `size_mb` | megabytes this level wrote or holds at its destination |

**The stage keys are `module`, `share` and `backup`, and they are the same three words everywhere** —
the stage table, the log file names, the JSON keys, the Go identifiers and the log subjects. There
is no second vocabulary and no translation anywhere in the run.

**This directory format is the specification, and `src/build/resources/backup/` is not.** The
skeleton committed there was a sketch of this section written as files; with the format stated here
it is redundant, so **delete `src/all/supervisor/src/build/resources/backup/` entirely**. Nothing
generates it, nothing reads it, and a second copy of a format that only Go writes could only drift.

**The filesystem is still the truth about a backup; `status.json` is the truth about a run.** A
module backup exists at its final name only if it succeeded, and its timestamp says when — that has
not changed and no status document overrides it. What `status.json` adds is the things the
filesystem cannot say: which stage failed, how long each took, how full each destination is, and
which modules were even attempted.

### Metric wiring

Three metrics read the newest `status.json` and nothing else. The plugin resolves the newest run
directory by stamp, reads the document, and publishes through the existing record cache, so the
display, the broker and the database all follow with no further wiring.

| Metric | Reads | Rule |
|---|---|---|
| `host/failed_backups` (`Fail BKP`) | each stage's `success_bool` | `failed ÷ 3 × 100`, so `0` / `33` / `67` / `100`; red if not `0` |
| `host/used_backup_space` (`Used BKP`) | the run-level `disk_usage_perc` | amber above `90`, red above `95` |
| `service/backup_status` (service `BKP`) | that module's `success_bool` under `stage.module.module` | true is healthy, which `Truthy()` already expresses |

Mapping onto the two-boolean colour model the display already uses (`pulse=false` is red,
`pulse=true` with `trend=false` is amber):

- **`Fail BKP`** — `pulseRule: Bounded(Self, Exactly, 0)` and `trendRule: Bounded(Self, Exactly, 0)`,
  which is what it declares today. Only the value changes: the stub becomes the failed-stage share.
- **`Used BKP`** — `pulseRule: Bounded(Self, AtMost, 95)`, `trendRule: Bounded(Self, AtMost, 90)`,
  replacing today's 90/80, so the thresholds are the ones stated above rather than inherited from a
  placeholder. It reads `/backup` and nothing else, so **a host with no `/backup` mounted errors**
  and paints the blank-and-alert "could not measure" state rather than reporting an inert green
  zero. That is deliberate and is the opposite of how `spin_fan_speed` treats a fanless host: a
  missing fan is a permanent fact about the hardware, whereas a missing `/backup` means the disk
  this metric exists to watch was not there — `jen`'s is `mad`'s over samba and its absence is a
  real fault, not a property of the Pi.
- **`service/backup_status`** — `Truthy()` on both rules, replacing today's `Always()`. `Always()` is
  what makes the current stub green regardless, and it is exactly the "declaring itself healthy
  whatever it holds" pattern `host/services` was converted away from.

Each metric's `description` in `metricBuildersByID` loses its `not yet implemented` /
`always true until implemented` clause, and each keeps stating its numbers through constants on the
plugin rather than as literals in two places.

**Staleness is the plugin's judgement, and it is derived rather than written.**
`backupStaleWindow` is `24h + backupRunCeiling` — **29 hours** — so the allowance for a run to
complete is the same five hours that bounds the leader's lease and the run itself, stated once in
`plugin_backup.go` and never as a literal at a call site. A run
directory is *current* when its stamp is within `backupStaleWindow` of now **and** it holds a
`status.json`. When no current run exists:

- **`Fail BKP` reads `100`**, since every stage has failed to produce a result
- **`service/backup_status` reads `false`** for every module
- **`Used BKP` holds its last value**, because disk usage does not become unknown just because a run
  was missed, and reporting `0` would paint a confidently green box. With no last value — a
  supervisor that has just started and has never seen a `status.json` — the metric **errors**, which
  is the blank-and-alert "could not measure" state, exactly as an unreadable sensor does.

The last-value carry is **in-process only**: supervisor holds no persistent state across restarts,
so a restart with no current run leaves `Used BKP` blank until the next run writes a status
document. That is the honest reading and it is preferable to persisting a number whose age nothing
would then report.

**The reads are cache-period work, not per-poll work.** `status.json` changes at most once a day, so
the plugin parses it on the `--cache-period` refresh and on the pulse following a run it performed
itself, exactly as `probe_mounts.go` treats its snapshot. The three metrics declare `warming: true`
where they can report before the first read, and the derivation names the run directory and its age
so a stale reading explains itself without a debugger.

### What this needs that does not exist yet

Two prerequisites, both unchanged in substance from the previous design and both still open:

**Four packages in the image.** `docker_deps_base.txt` carries `mosquitto-clients`, `jq` and
`smartmontools` and none of these:

| Package | Needed by |
|---|---|
| a docker client | the module stage — each module's script runs `docker exec` and `docker stop`/`start` |
| `rsync` | the share and backup stages |
| `cifs-utils` | `mount.sh` on `jen`, for the two samba mounts |
| `util-linux` | `mountpoint`, the guard both stages and `mount.sh` depend on |

All four are base rather than build packages, since they run in the shipped image. Add the names,
run `fab generate`, then paste the pinned `RUN` block from `docker_deps.sh` into the `Dockerfile`.

**Same-path mounts replacing the read-only `/:/host`.** Mount the directories the driver needs at
the paths they already have on the host, so the script the driver runs is the same script, at the
same path, reading and writing the same places, whether invoked from a shell on the host or from
inside `supervisor`:

| Mount | Mode | Why |
|-------|------|-----|
| `/var/lib/asystem/install` | `ro` | each module's `backup.sh` and its `.env` |
| `/home/asystem` | `rw` | the module data directories, where `backup/` is written |
| `/share` | `rw` | the share stage's destination |
| `/backup` | `rw` | the backup stage's destination |
| `/var/run/docker.sock` | `rw` | already mounted — `exec` into a module, and `stop`/`start` for offline copies |

**`/share` and `/backup` must be bound `rshared`, or `mount.sh` mounts into a namespace nobody
sees.** A mount the container makes under a default private bind is invisible to the host, and — the
half that actually bites — a mount the *host* makes afterwards is invisible to the container, which
is exactly `jen`'s automatic `/share/10` fstab mount. Both directions need mount propagation, so
these two entries carry `:rshared` (and the host's own `/share` and `/backup` must be shared mounts
for the kernel to allow it). This is the one prerequisite that is not merely a package or a path,
and it should be proved on `jen` before the share stage is written anywhere else.

**`BROKER_TOKEN` is not in `docker-compose.yml`'s `environment:`**, though `checkexecuting.sh`
already reads it — the `${BROKER_TOKEN:+…}` form makes it connect anonymously today. If the broker
requires credentials for the tasmota command topic, that variable has to be named there before
`mount.sh up` can switch the plug.
Three consequences, all simplifications:

- **no prefix awareness.** A path is a path. Nothing has to know whether it is running in a
  container, and no `SUPERVISOR_MOUNT`-style rewriting is needed on a module's script. `/` is
  currently mounted at `/host` read-only, which would have forced exactly that rewriting on every
  module script
- **nothing is spawned.** The plugin executes the module's script directly. The throwaway container
  earlier designs proposed is unnecessary and should not be built
- **`OFFLINE` is ordinary module logic.** A script running inside `supervisor`'s container can
  `docker stop` a *different* container without dying, so stop-copy-start needs no sidecar, no
  separate execution mode and no driver involvement

**The probes keep reading `/host`.** `probe_mounts.go`, `probe_logs.go`, `probe_sensors.go` and
`probe_install.go` all rebase through `$SUPERVISOR_MOUNT`, so the read-only root bind stays; the
four mounts above are added beside it rather than replacing it.

### How a module's script is executed

**One mode, always `${SERVICE_INSTALL}/backup.sh`.** The script runs in supervisor's container and
execs into its own container only if it needs something in there. The driver never chooses between
modes, never passes the script on stdin, and never needs a sidecar. `${SERVICE_INSTALL}` is
versioned and freshly copied each release, so the script that runs is always the current one.

**The plugin applies a deadline and the script does not.** `backup_awaited` in `influxdb3` waits
forever by design — waiting is the script's job, giving up is the scheduler's — so the plugin runs
each module under a `context.WithTimeout` and kills it on expiry. Nothing corrupts: the server-side
backup continues and the next run's status poll finds it. The per-module and per-stage timeouts are
constants on `plugin_backup.go`, and both sit under `backupRunCeiling`, which bounds the whole run
and from which `backupStaleWindow` is derived.

**A lock, so a scheduled run and a hand run cannot collide.** `install.sh`'s `run_backup` can fire at
any moment during a release, including inside the daily window. The plugin holds a `flock` on the
run root for the whole run and skips with a logged reason if it is held; a module's own
`BACKUP_SKIP_HOURS` throttle is the second line of defence and makes the collision harmless rather
than merely unlikely.

## Boundary with Go — planned

The division moved. Go is no longer only the scheduler: it is the driver, and shell is only ever a
module's own knowledge of its own data.

| | Owns | Must not |
|---|---|---|
| a module's `backup.sh` | what is safe to copy, how to produce it, its own throttle, its own pruning, its own vocabulary | know the schedule, the stages, `/share`, `/backup`, the status document or any metric |
| `plugin_backup.go` | when to run, discovering the modules, ordering and timing the stages, the `/share` and `/backup` copies, deadlines, the lock, writing `status.json`, judging staleness, feeding the three metrics | inspect a data directory, choose an exclusion, parse a backup format, contain a module name, or know a device topic, an fstab line or a mountpoint |
| `mount.sh` | the switch, the readiness wait, the fstab entries, the `mountpoint` assertions | know a module, a stage, a backup format, the schedule or the status document |

If any side reaches into another's right-hand column, the split has failed. The test for the plugin
is that it contains **no module-specific line and no estate-specific literal** — no
`rack_backup_plug`, no `/share/10`, no `cifs`; it calls `mount.sh up` and reads an exit code. The
test for `mount.sh` is that it makes no decision that depends on which host it is running on. The
test for a module script is that it still runs correctly by hand with no supervisor process
anywhere.

**Exit codes still matter**, because a module's script remains a hand-runnable program:

| | |
|---|---|
| `0` | backed up, or legitimately skipped by its own throttle |
| non-zero | failed — the plugin records `success_bool: false` for that module and does not promote it |

The plugin's own outcome is `status.json`, not an exit code — it is a daemon, not a command.

## Generation — built

### Why generate

Measured before building it: `postgres` and `mariadb` differed by **four lines** once the module
prefix and the dump command were normalised, and the listing/epoch/prune helper block was
**byte-identical** between `postgres` and `letsencrypt`. Of 78 lines, roughly 70 were boilerplate —
and they were precisely the lines carrying the hazards: implicit self-exclusion, atomic rename,
metadata preservation, keeping the newest backup regardless of age, sweeping stale `.tmp`, and not
pruning after a failure. Generating them fixes each hazard once instead of once per module.

The snippets that replaced those scripts total **under 90 lines**, of which `influxdb3` is 63.

### Shape, following `write_container_healthchecks()`

| | health checks | backup |
|---|---|---|
| wrapper | a template in `container.py` | a template in `container.py` |
| module part | `src/build/resources/check{alive,executing,healthy}.sh` | `src/build/resources/backup.sh` |
| output | `src/main/resources/image/check*.sh` | `src/main/resources/backup.sh` |
| stub if absent | written with a `TODO` | written with a `TODO` |
| call site | the module's generate script | the module's generate script |
| enrolment | calling the function | calling the function |
| banner | yes, never hand-edit the output | yes, never hand-edit the output |

One deliberate divergence: `write_container_healthchecks()` joins its fragment into a **single
line**, which is why those fragments may not contain comments. A backup snippet is inserted as
multi-line shell, so it may. Do not copy the one-lining across — it exists only so a health check can
be one `test` expression.

### Overriding by redefinition

The snippet is inserted **after** the wrapper's definitions and **before** the main flow, so a module
overrides anything simply by redefining it. There is no hook protocol, no registration, and no
parameter describing what a module overrides:

- `postgres`, `mariadb`, `zigbee2mqtt` define `backup_written`, naming a `_full` backup with
  their own extension
- `letsencrypt` and `plex` define `backup_written` as a call to `backup_files` with their paths
- `influxdb3` defines `backup_written`, adds its own full/delta helpers, and keeps its state under
  its own `INFLUXDB3_BACKUP_*` names

`backup_written` is the one definition a snippet may not skip — the wrapper's only prints why it is
missing and returns non-zero.

Repetition between snippets is preferred over parameters on the generate call. Each snippet reads
like the one command that module actually needs.

### Failure leaves nothing behind

The backup's existence at its final name is the **only** success signal, and it is structural
rather than a convention a reader has to know:

```bash
trap backup_discarded EXIT
if backup_written && [ -n "${BACKUP_TARGET_PATH}" ] && [ -s "${BACKUP_TARGET_PATH}.tmp" ]; then
  mv "${BACKUP_TARGET_PATH}.tmp" "${BACKUP_TARGET_PATH}"
```

Everything is written to `.tmp` and renamed only on success, so a consumer never sees a partial file
under the final name — `mv` within a filesystem is atomic. `backup_discarded` runs on **every** exit
path, including a crash or a kill, removing the `.tmp` and the stamp directory if no backup
landed. A failed run therefore leaves no file and no empty directory.

`status.json` follows the same rule for the same reason — written to `.tmp`, renamed on completion.

A `.sha256` sidecar was considered and rejected: every backup is `.gz` or `.zip`, whose container
formats already carry CRC32, so `gzip -t` detects corruption without a second file to keep in step.
If periodic integrity checking is ever wanted, that is the mechanism, not a sidecar.

### Classifying a backup

```bash
backup_is_full() { [[ "${1}" == *"${BACKUP_FULL_SUFFIX}".* ]]; }
backup_is_delta() { [[ "${1}" == *"${BACKUP_DELTA_SUFFIX}".* ]]; }
```

These are what let the share stage apply GFS to a module it knows nothing about: a `_full` may be
kept as a weekly or monthly point, a `_delta` only inside the dense window.

## Copy rules

**module to share is additive** — `rsync -a` without `--delete` — in both shapes. Mirroring here
would propagate the module stage's seven day window to the share stage, and no history longer than a
week could exist anywhere. `--link-dest` against the previous copy makes an unchanged backup cost an
inode rather than its bytes.

**The share stage thins, then the backup stage mirrors.** The plugin copies from the module stage,
applies the GFS policy to what it holds, then replicates the share to `/backup`. The share stage is
the only one that deletes a backup on purpose.

**A host writing to a borrowed share copies to a disk it does not own, and that is fine.** On `jen`
both `/share/10` and `/backup` are `mad`'s, reached over samba, so `jen`'s share stage writes into
`mad`'s share and its backup stage is a no-op for every `/share/<n>` but the one it mounted — `mad`
replicates its own shares on its own run. The `mountpoint` guard is what keeps that honest: `jen`
sees exactly one mounted share and replicates exactly that.

**The backup stage covers every share, not just the one the share stage writes to.** The share stage
only ever touches `/share/<index>0/backup/`, but the backup stage replicates `/share/*` into
`/backup/share/*`, so the media and data on a host's other shares are carried by the same job.

**`--delete` everywhere except `backup/`, and that choice decides where retention actually bites:**

| Backup-stage path | `--delete` | Consequence |
|---|---|---|
| `media/`, `service/` | **yes** | a file deleted on the share disappears, which is what a mirror is for |
| `tmp/` | — | not replicated at all; scratch, and large enough to be worth skipping |
| `backup/` | **no** | the backup stage keeps every backup the share stage ever held, including ones since thinned |

So **the GFS policy bounds the share stage, not the backup stage**. The backup stage is append-only
for backups and grows by the thin churn — a full and its deltas per week, a full per month — which
at these volumes is small beside the media on the same disk. What it buys is that a mistaken or
buggy thin at the share stage cannot reach the only remaining copy: the two can never be wrong in
the same way at the same time.

The alternative is `--delete` on `backup/` too, making the backup stage an exact mirror and bounding
both by the same policy. That is tidier and cheaper, and it is the right change if the backup disk
ever grows uncomfortably — but it removes the second copy's independence, so a single bad prune at
the share stage would take both. Not worth it while the backups are this small.

Either way, **nothing at the backup stage prunes on its own**. If `backup/` is append-only it needs
an eventual ceiling, and that ceiling is the only retention this document does not yet specify.

## Retention, share stage — planned

**The sparse tail lives at the share stage, because the backup stage is a mirror and a mirror cannot
thin.** Whole-share replication copies what it finds; it cannot also be the thing that keeps twelve
monthly points and discards the rest. So the share stage owns the policy and the backup stage
replicates the outcome.

**The volumes are not all alike, and this is what the full/delta design is about.** The SQL dumps,
the zigbee coordinator backup and the letsencrypt tar are small and stay small — a full copy of each
at every retention point costs nothing. InfluxDB is the opposite: it accumulates continuously and
will grow without bound, which is precisely why it takes incremental backups instead of full ones.

That creates a tension the sparse tail has to answer for, because **a sparse restore point must be
self-contained, and for a `DELTA` module that means a `_full` — a complete copy.** Daily deltas are
cheap; twelve monthly points are twelve full copies of a growing store. GFS at the monthly tier
therefore reintroduces exactly the cost deltas exist to avoid, for the one module where it hurts.

Three ways to answer it, and the right one depends on growth rather than on today's size:

- **shorter monthly depth for InfluxDB than for everything else** — the retention knobs should be
  overridable per module (`<MODULE>_BACKUP_KEEP_MONTHLY` and friends) rather than one estate-wide
  policy, which the env-driven convention already supports
- **longer runs between fulls** — one full and many deltas, so the tail is cheap, at the cost of a slower
  restore and a larger blast radius if a link is corrupt
- **deduplication** — a `restic`/`borg` repository fed from the share stage, which is where its value
  actually lies, since it makes twelve monthly fulls cost close to one

That third option was rejected above on the grounds that volumes are small. **That reasoning holds
for five of the six modules and expires for InfluxDB**, so the decision is *not yet*, not *no* —
revisit when the object store passes a few GB.

Two things accepted meanwhile: monthly backups sit at **full size on both disks**, which is only a
real cost for InfluxDB, and there is **no integrity verification** beyond the filesystem's — nothing
detects a silently corrupted backup until a restore needs it.

Granularity tracks detection latency: caught in a week, caught this month, caught this year.

| Tier | Points | `FULL` | `DELTA` |
|------|--------|--------|---------|
| daily | 7 | the 7 newest backups | every increment inside the window |
| weekly | 4 | newest per ISO week | that week's `_full`, its deltas dropped |
| monthly | 12 | newest per month | that month's first `_full`, its deltas dropped |

A sparse restore point must be self-contained, so it must be a **`_full`** — which is exactly what
the filename suffix declares, and why the share stage can apply this policy without knowing which
module it is looking at. Deltas are only ever retained inside the dense window.

**The share stage must not thin blindly**, and the `_full` / `_delta` suffix is what stops it having
to guess. Dropping a `_full` destroys every `_delta` after it, so the share stage keeps `_full`
backups as its weekly and monthly points and retains `_delta` backups only inside the dense window.

**So the share stage delegates: it calls the module's own `backup.sh --prune <dir>` against the
share directory.** The stage decides the policy — which points to keep, from the GFS knobs in the
environment — and the module enacts it on backups it alone understands. A `FULL` module reuses its
default pruning against a different directory; `influxdb3` applies its own rule. No new script and
no new hook, and the plugin never learns which module it is thinning.

It also falls out of the module-stage design for free, because pruning was already an overridable
step; the only change is that it takes the directory to work on rather than assuming its own.

## Restore

| Module | Procedure |
|--------|-----------|
| `influxdb3` | untar the `_full` and every `_delta` after it, in order, into an empty object store — a `_delta` is meaningless without the `_full` it hangs off |
| `postgres` | `gunzip -c all_<stamp>.sql.gz \| psql -U postgres` |
| `mariadb` | `gunzip -c all_<stamp>.sql.gz \| mariadb -uroot -p` |
| file copy | restore the backup over the data directory, then redeploy the module so the git-managed files return |

For anything older than the module stage's window, restoring in place is rarely right — rolling a
database back a month discards a month of good data. Stand the copy up beside production, compare,
and extract the range that matters.

HA's configuration lives in `homeassistant` but its recorder lives in `postgres`, so restoring HA to
a day needs both at that day. A single daily pass produces same-day backups minutes apart: not
transactional, but a loose estate-wide restore point, and a reason to keep every module on one
schedule rather than letting them drift onto their own. That is also why the module stage runs
**serially** rather than in parallel — the backups are minutes apart rather than concurrent, and a
parallel run would put six modules' load on one host at once for no gain a nightly window needs.

## Gaps and decisions

**Open** means an answer is still needed from a human; **gap** means something is missing or wrong
with no question attached. Ordered by what would hurt most.

| # | Item | State | Blocks |
|---|------|-------|--------|
| 1 | No restore has ever been tested | gap | trusting any of this |
| 2 | influxdb3 keeps two copies and prunes neither | **defect** | running daily |
| 3 | The driver is not built — `plugin_backup.go` does not exist | gap | daily backups, the share and backup stages |
| 4 | Backups are readable on the public samba share | accepted | — |
| 5 | The backup stage does not exist, and has no ceiling of its own | gap, decided | off-host |
| 6 | Five modules need a script, four need a verdict | gap, partly **open** | knowing this is sufficient |
| 7 | Nothing reports backup health | gap | — |
| 8 | Nothing has been sized | gap | backup-stage sizing |
| 9 | No automated tests | gap | — |
| 10 | Detection latency dominates retention depth | gap | — |
| 11 | A module's script has no lock | gap, minor | — |
| 12 | `Fail BCK` is labelled inconsistently with its metric | gap, decided | — |
| 13 | The cluster singleton is not built | gap | switching the outlet off |
| 14 | `mount.sh` does not exist, and mount propagation is unproven | gap | the share and backup stages |

No item is blocked on a decision any more. The only judgement left is inside **6** — four modules
whose verdict needs a look at what they actually hold, which is research rather than a question.

Out of scope, deliberately: media and user data on `/share/<n>/{media,service}`, which is not
module state — though it shares the `/backup` disk and the backup stage, so it is out of scope for
*policy* while riding along in the same replication; and build-time secrets such as `.env_all_key`,
already covered by the `fab backup` task that rsyncs git-ignored files to `~/Backup/asystem/`.

### 1 No restore has ever been tested — gap

Every mechanism here is verified; no restore is. Restore each kind into a scratch target and record
the result: an influxdb3 `_full` plus its `_delta`s into an empty object store, a `pg_dumpall` into a
throwaway postgres, a `mariadb-dump` likewise, and a file-copy tar over a data directory. influxdb3 is the
one most likely to surprise, being the only backup that is not self-contained. The output of that
exercise is the per-module restore runbook, which also does not exist. The `letsencrypt` tar has been
round-tripped into an empty tree with symlinks and `0600` modes intact — that is the closest thing to
a tested restore so far, and it is not a service restore.

Note the influxdb3 restore shape **changed** when it moved to generation: backups are now gzipped
tars of individual backup directories rather than the object store's own layout, so a restore means
untarring the `_full` and each `_delta` in order back under `{{cluster_id}}/backups/` before invoking
influxdb3's restore. That path has never been exercised.

### 2 influxdb3 keeps two copies and prunes neither — defect

Introduced by moving influxdb3 onto the generated wrapper, and not yet fixed. Its snippet calls
`influxdb3 create backup` and then tars the resulting directory into `backup/`, which means:

- **the server-side set is never pruned.** Nothing calls `influxdb3 delete backup`, so
  `${SERVICE_DATA_DIR}/cluster_1/backups/` accumulates every full and delta ever taken, for ever.
  The wrapper's `backup_pruned` only reaps `backup/<stamp>` directories — our tars — and never
  touches what the server holds.
- **every backup exists twice on disk**, once as the server's directory and once as our gzipped tar.
  The hand-written version avoided this with a hardlinked export that cost nothing.

Both land on the one module that actually grows, which is the worst place for them. The fix is a
handful of lines in the snippet: after a successful tar, delete the server-side backup whose contents
were just captured, keeping only what a restore needs — and honouring the cascade, since deleting a
full removes its deltas. Must be fixed before anything runs this daily.

### 3 The driver is not built — gap

Every module's `backup.sh` works, can be run by hand, and is called at release time by
`install.sh`'s `run_backup`. Nothing calls them on a schedule, and the share and backup stages do
not exist. The build order is the one thing this document adds:

1. **`--daily-time` and the gate** — `config.DefaultDailyTime`, `Periods.DailyMinutes`, the flag on
   `cmd_serve.go`, and `isDaily` threaded through `probe.Run`'s `onPulse`. Testable on its own, with
   no backup behaviour behind it, and it is the piece anything else daily will reuse.
2. **`plugin_backup.go` and the module stage** — the supervisor module backup, then each enrolled
   module serially, writing the log tree and `status.json`. Stops there: it is a complete, useful
   daily backup with no `/share` involvement.
3. **The metrics** — `Fail BKP`, `Used BKP` and service `BKP` off the status document, with the
   `backupStaleWindow` rule. Depends on 2 and nothing else.
4. **The bind mounts and the packages** — `/home/asystem`, `/share`, `/backup`, and the docker
   client, `rsync`, `cifs-utils` and `util-linux` in `docker_deps_base.txt`. The `/home/asystem`
   bind and the docker client are needed before 2 runs anywhere real; the `/share` and `/backup`
   binds, their `rshared` propagation and the other three packages are only needed by 5.
5. **`mount.sh` and the mounts** — the switch, the readiness wait, the fstab-driven mounting, and
   the `rshared` binds proved on `jen`. Independently testable by hand (`mount.sh up`, look at
   `mountpoint`, `mount.sh down`) with no backup behaviour behind it.
6. **The cluster singleton** — the retained-topic mutex, the will, the lease. Testable against a
   scratch broker with no disks involved, and it is the only piece with a concurrency hazard.
7. **The share and backup stages** — the `rsync` pair with `--temp-dir`, the GFS thin by
   delegation, the `mountpoint` guards, gated on the election and on `mount.sh up` succeeding.

A per-host cron calling each `${SERVICE_INSTALL}/backup.sh` remains a reasonable interim if daily
backups are wanted before step 2 lands — it needs nothing that does not already exist.

### 4 Backups are readable on the public samba share — accepted

`storage/install_prep.sh` publishes every `/share/<n>` as `public = yes`, `read only = no`,
`create mask = 0666`, so once the share stage runs, database dumps — and HA's `secrets.yaml` and
`.storage/auth` when that module gains a script — are readable by anything on the LAN reaching
samba. They cannot be excluded, because a restore needs exactly those files.

**Accepted, deliberately.** The two fixes considered were moving `backup` outside the published tree
and giving it its own restricted share; both were rejected as cost without benefit at this trust
boundary. The LAN is the boundary, `jen` reaches `mad`'s share as an ordinary samba client, and the
same share already carries everything else this estate holds.

Two consequences to keep in view rather than act on. **Writable matters more than readable** —
`read only = no` means a LAN client can *delete* a backup, so samba exposure is a availability risk
before it is a confidentiality one, and it is the share stage's copy that is exposed while the
module stage's copy under `/home/asystem` is not. And this is the argument that would have justified
encryption at rest, which is recorded as decided against below; if that is ever revisited, this is
the reason it would be.

### 5 The backup stage does not exist — gap, design decided

Everything lives on the machine it protects, so a dead host loses the module and share stages
together.

The shape is settled: the backup stage is the replication of `/share` to `/backup`, module backups
riding along in the `backup/` subtree, and **the share stage owns the GFS thinning** because a
mirror cannot thin. A `restic`/`borg` repository alongside it was considered and rejected at these
volumes — revisit only if the volumes ever justify it. Nothing new has to own it: whatever
replicates `/share` to `/backup` does the job, with `backup/` excluded from `--delete` so a mistaken
thin cannot reach both copies.

Until then, **the share stage has no retention at all** — the copy from the module stage is
deliberately additive, so nothing on the share is ever deleted.

And once built, **the backup stage still has no ceiling of its own**. `backup/` is deliberately
excluded from `--delete`, which means it accumulates every backup the share stage ever held.
Affordable at current volumes, and the last retention this document does not specify — see *Copy
rules* for the trade and the alternative.

### 6 Five modules need a script, four need a verdict — gap, partly open

Every module that runs a container, whether it holds state and what to do about it. **Required** is a
proposal from reading mounts, run-dependencies and shipped data, not a finding — confirm each before
acting. The remaining directories under `src/` have no `docker-compose.yml` at all: they are host
configuration and tooling, with no container and no service state.

| Module | Host | Backup | Required | Suggested implementation |
|--------|------|--------|----------|--------------------------|
| `influxdb3` | max | ✅ `DELTA` | — | snippet defines `backup_written` and adds full/delta helpers |
| `postgres` | mad | ✅ `FULL` | — | `docker exec postgres bash -c 'pg_dumpall -U postgres \| gzip' >"$1"` |
| `mariadb` | meg | ✅ `FULL` | — | `docker exec mariadb bash -c 'mariadb-dump --all-databases --single-transaction \| gzip' >"$1"` |
| `zigbee2mqtt` | jen | ✅ `FULL` | — | MQTT bridge request, base64 zip off the response topic |
| `letsencrypt` | may | ✅ `FULL` | — | `backup_written` calling `backup_files` with its paths |
| `plex` | mad | ✅ `FULL` | — | `backup_files` of `Preferences.xml` and `Plug-in Support/Databases`, service stopped for the copy |
| `homeassistant` | meg | ❌ | **yes** | prefer its backup integration — POST to the API with the `HOMEASSISTANT_API_TOKEN` already in its environment, then collect the tar it writes. Fallback: `INCLUDE=.storage` with `OFFLINE`. Note its native path is `/config/backups`, one letter from ours |
| `sonarr` | may | ❌ | **yes** | `sonarr.db` and `config.xml`. Sonarr's v3 API is believed to expose a Backup command — verify before relying on it; otherwise `OFFLINE` with `backup_files` |
| `sabnzbd` | mad | ❌ | **yes** | `sabnzbd.ini` and `admin/` (history and queue databases, written live) — `OFFLINE` with `backup_files` |
| `grafana` | may | ❌ | **yes** | users, API keys and preferences in `grafana.db`; dashboards come from jsonnet so are not needed. `sqlite3 grafana.db ".backup $1"` is online-safe, else `OFFLINE` with `backup_files` |
| `mlflow` | max | ❌ | **yes** | **not visible in a data-directory scan** — its backup root is a share mount, `/share/1/service/mlflow/backups` in production. Experiment metadata is in `postgres` and already covered; the backups are not. A tar of the backup root, or a deliberate decision that backups are reproducible |
| `rhasspy` | zzz | ❌ | verify | trained voice profiles, if any are trained — `backup_files` the profile directory, else declare derived |
| `openra` | max | ❌ | verify | settings and replays; low value, most likely declare derived |
| `appdaemon` | zzz | ❌ | verify | apps come from git — check whether anything generated is kept alongside them |
| `vernemq` | meg | ❌ | verify | retained messages, but its store is `tmpfs` and every module republishes its own on deploy, so most likely derived |
| `weewx` | jen | ❌ | no | writes to the `mariadb` weewx database; configuration and skins from git |
| `wrangle` | mad | ❌ | no | writes to `postgres` |
| `network` | mad | ❌ | no | writes to `influxdb3` and MQTT |
| `tempstat` | may | ❌ | no | writes to MQTT |
| `nginx` | meg | ❌ | no | configuration generated, certificates pulled from `letsencrypt` |
| `cloudflare` | may | ❌ | no | configuration generated, credentials from the environment |
| `supervisor` | all | ❌ | **driver** | no generated script — its own state is copied by the supervisor module backup, the first step of the module stage |
| `mlserver` | max | ❌ | no | mounts `mlflow`'s backup root; no state of its own |
| `monitor` | zzz | ❌ | no | host paths mounted read-only |
| `unpoller` | zzz | ❌ | no | no volumes |
| `redpanda` | zzz | ❌ | no | no volumes |

Two things this table changed. **`mlflow` was missed** by the original inventory because it holds no
`${SERVICE_DATA_DIR}` — presence of a data directory is not the same as holding state, and any
future module mounting a share needs the same second look. And **`homeassistant` is the last open
mechanism question**, now that `zigbee2mqtt` has settled the pattern for a module with a native API
and `plex` has settled the `OFFLINE` file-copy pattern.

Order of work, once confirmed: `homeassistant` (largest irreplaceable state), then `mlflow`
(silently uncovered today), then `sonarr`, `sabnzbd`, `grafana` — all three of which are the same
`OFFLINE` file-copy shape `plex` now demonstrates.

### 7 Nothing reports backup health — gap

`backupStatus()` returns a bare `true` (`internal/probe/probe_services.go`), and `failedBackups()`
and `usedBackupSpace()` return `errUnimplemented` (`internal/probe/probe_host.go`), so a
persistently failing backup is visible only in a log even though the measures and the Home Assistant
entities already exist. *Metric wiring* above specifies all three; it depends on item 3 step 2 and
on nothing else.

### 8 Nothing has been sized — gap

Partly answered by the backup-stage finding: module backups share the `/backup` disk with the media,
which dwarfs them, so *will it fit* is no longer the worry it looked. What is still unmeasured is the
influxdb3 object store, the dump sizes, and what the per-release `cp -rfpa` of the backup tree costs
at the current cadence. Two commands settle it:

```bash
du -sh /home/asystem/*/backup
du -sh --count-links /home/asystem/influxdb3/latest/cluster_1/backups   # vs without
```

The second also answers whether influxdb3 fulls share storage, which decides how many sparse
restore points are affordable. Once the driver runs, `status.json`'s `size_mb` and `file_count`
answer the first continuously and this becomes a query rather than an exercise.

### 9 No automated tests — gap

The scripts have been exercised by hand against stubbed CLIs in a container, but nothing runs in
`fab ut` or `fab st`. The full/delta logic in particular — when to start a new full, and the rule
that keeps a full predating the window — is the kind of thing that breaks silently on a later edit.

The Go half is more testable and should not repeat that: the daily gate is a pure function of a
clock and a configured minute, `status.json` parsing and the three metric derivations are pure
functions of a document, and `backupStaleWindow` is a table-driven case per outcome — including the
no-last-value case, which must produce a blank rather than a zero.

### 10 Detection latency dominates retention depth — gap

A year of monthly copies only helps if the damage is eventually noticed. Scheduling `describe.sh`
and diffing its output would shorten time-to-notice far more cheaply than lengthening the tail, and
supervisor's daily gate is the obvious place to hang it — a second consumer of `isDaily`, which is
why the gate is generic infrastructure rather than a backup callback.

### 11 A module's script has no lock — gap, minor

Two concurrent runs of the same module's `backup.sh` inside one second would share a stamp and race
on the same `.tmp`. The `BACKUP_SKIP_HOURS` throttle makes it unlikely rather than impossible, and
the plugin holds a lock of its own, but the collision that matters is a release-time `run_backup`
landing inside the daily window — so a `flock` on `BACKUP_INTERNAL_ROOT_DIR` in the wrapper is what
closes it properly.

### 12 `Fail BCK` is labelled inconsistently with its metric — gap, decided

The metric is `host/failed_backups` and every other name here is `BKP` — `Used BKP`, service `BKP` —
but both display layouts label it `Fail BCK` (`display_layout.go`). **Rename the label to
`Fail BKP`**, in the compact and relaxed layouts alike. It is a label change only: the metric name,
the topic, the column and the box geometry are all untouched, and both labels are nine characters so
no row's pre-resize width moves and `Compile`'s equal-width assertion still holds. The cost is
60-odd occurrences of mechanical churn in `display_test_layouts.go`.

### 13 The cluster singleton is not built — gap

The protocol is specified under *The cluster singleton* and nothing is written. It is the one piece
here with a genuine concurrency hazard, so it should be built and exercised before the share stage
depends on it: run four `serve` processes against a scratch broker, have them all claim at once, and
assert exactly one leads; kill the leader and assert the will clears the lease; expire a lease and
assert the next candidate claims it. All three are broker-level tests needing no disks.

Two numbers are still guesses and should be measured rather than reasoned about:
`leaderSettle`, which must exceed the broker round trip by a comfortable margin, and
`mountReadySeconds`, which is however long the drives actually take from relay close to enumerated.

### 14 `mount.sh` does not exist, and mount propagation is unproven — gap

The script is specified above and nothing is written. The part to prove first is not the script but
the **`rshared` bind**: a mount made inside the container must be visible on the host and, more
importantly, `jen`'s fstab-mounted `/share/10` must be visible inside the container. If propagation
cannot be made to work, the fallback is to run `mount.sh` on the host by way of the install tree
rather than inside the container — which reintroduces exactly the "a container cannot execute a host
script" problem the same-path mounts were adopted to remove, so it is worth proving properly.

`jen`'s fstab is yours to write and this plan assumes two entries: `/share/10` as `cifs` and
automatic, `/backup` as `cifs` and `noauto`. The script reads whichever it finds, so a different
shape changes nothing in the Go and nothing in this document beyond the table.

### Closed during design and build

- **Powering and mounting** — a supervisor-owned `mount.sh`, hand-authored, phased `up`/`down`,
  driven by `/etc/fstab` rather than by a host list, with the plug published to over MQTT. The
  plugin calls it and reads an exit code, so no device name, mountpoint or filesystem type reaches
  the Go.
- **Who switches the outlet off** — a leader elected daily over MQTT with a retained-topic mutex, a
  last will and a five-hour lease, running power-on as its init and power-off as its destroy. The
  module stage sits outside it entirely, so a failed election costs a promotion and never a backup.
- **Interrupted copies** — `--temp-dir` on every `rsync`, wiped before each stage, with `--partial`
  and `--inplace` both rejected. A hard reset costs one file's transfer and leaves nothing a later
  run could mistake for data.
- **`hot` / `warm` / `cold`** — retired in favour of `module` / `share` / `backup`, one word per
  stage named for what it writes to, used identically in the prose, the JSON, the log file names and
  the Go.
- **Supervisor's own `backup.sh`** — retired. The driver is `plugin_backup.go`; supervisor is not
  enrolled through `write_container_backup()` and its own state is copied by the supervisor module
  backup at the head of the module stage.
- **Release-time triggering** — not retired, relocated. Per-module `install_prep.sh` hooks are gone
  and the root `install.sh`'s `run_backup` is the single release-time call site, complementary to
  the daily run rather than competing with it.
- **Encryption at rest** — decided against. Backups stay in the clear at every stage. That also
  removes the one argument that would have justified `restic`/`borg` at current volumes, so the
  backup stage stays a plain mirror. Item 4 is the standing reason this might be revisited.
- **Samba exposure of the backups** — accepted rather than fixed; the LAN is the trust boundary and
  the same share already carries everything else. See item 4.
- **The three metric readings** — `Fail BKP` is `failed ÷ 3 × 100`, `Used BKP` is `/backup`'s own
  usage and errors where `/backup` is absent, and `service/backup_status` is that module's
  `success_bool` under `Truthy()`.
- **Generation** — `write_container_backup()` is built, six modules go through it, and the
  wrapper/snippet split is proven. No module is exempt, so no script exists that generation would
  not recreate.
- **Always run from the install directory** — one execution mode, no sidecar, no `bash -s`.
- **Per-module env vars** — `<MODULE>_BACKUP_ENABLED` / `_MIN_INTERVAL` / `_RETAIN_DAYS` /
  `_INCLUDE` / `_OFFLINE` / `_TIMEOUT` are all gone. Presence of the generate call is the enable;
  the policy values are overridable wrapper variables; everything else is a snippet variable.
- **`full` / `delta` naming** — one vocabulary from the backup filename down to influxdb3's
  server-side backup names, its snippet's `backup_stored` / `INFLUXDB3_BACKUP_STORE`, and its log
  lines. `base`, `inc` and `chain` are retired, in the code as well as the prose.
- **Dependency-aware thinning** — the `_full` / `_delta` suffix plus `backup_is_full` /
  `backup_is_delta` let the share stage apply GFS to a module it knows nothing about.
- **Share index** — the sixth field of `.hosts`, read by `_get_host_index()`, emitted into
  `config.json`.
- **How a container runs a host script** — same-path bind mounts; the sidecar proposal is withdrawn.
- **`OFFLINE` execution mode** — not a driver concern; a script in supervisor's container can stop a
  different container without dying.
- **`zigbee2mqtt` mechanism** — its bridge API over MQTT.
- **A `.sha256` sidecar** — rejected; every backup is `.gz` or `.zip`, whose formats already carry
  CRC32, so `gzip -t` detects corruption without a second file to keep in step.
- **A report file for the module stage** — still rejected *for a backup*: a backup's existence at
  its final name is its own success signal and no document overrides it. `status.json` is a record
  of **the run**, which is a different question, and is what the three metrics read.
- **`src/build/resources/backup/`** — deleted. The directory format is specified under *The run's
  output*; a committed skeleton of a format only Go writes could only drift from it.
- **influxdb3 excluding unpersisted data** — accepted, not fixed. A backup covers only what has
  reached object storage, so with `INFLUXDB3_GEN1_DURATION=10m` its restore point lags the SQL
  modules by up to the gen1 window. Inferred from the documented behaviour, not measured.
- **The dangling Time Machine reference** in `storage/install_prep.sh` names
  `${SHARE_DIR}/backup/timemachine`, which is no longer created; the block is disabled, so this is
  noted rather than open.
