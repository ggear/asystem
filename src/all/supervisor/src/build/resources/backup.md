  # Backup

How every stateful module is backed up, where the copies live, how long they are kept, and how to
restore. Status is marked per section: **built** is in the repo today, **planned** is not.

## Tiers

A copy is only worth what it survives. Three tiers, each protecting against the failure the one
before it cannot, and each thinner than the last — the retention goes from **dense** (every backup,
a week deep) to **sparse** (a year deep, a handful of points), because the further back you look
the less resolution is worth paying for.

| Tier | Location                                 | Protects against | Retention | Status |
|------|------------------------------------------|------------------|-----------|--------|
| **hot** | `/home/asystem/<module>/latest/backup`   | a bad release, an accidental delete, logical corruption | dense — 7 days | **built** |
| **warm** | `/share/<index>0/backup/<module>`        | loss of the service data directory or its filesystem | sparse — GFS, daily 7 / weekly 4 / monthly 12 | **planned** |
| **cold** | `/backup/share/<index>0/backup/<module>` | loss of the host or its primary share | mirror of warm, `backup/` append-only | **planned** |

**The warm tier is not off the host.** `/share/<n>` is a local ext4 partition
(`PARTLABEL=share_08 /share/10 ext4 …`), so a host that dies takes hot and warm with it. Warm
exists to get copies off the service data directory and onto a large disk a later process can pull
from. Only cold is a real backup.

**Cold is a subtree of a share replication, not a backup-specific job.** `/backup` is a separate
mounted disk that mirrors `/share`, and cold replicates **every** mounted share on the host —
`/share/*` into `/backup/share/` — not only the primary. `/backup/share/<index>0/backup/<module>` is
simply where the module backups land inside a copy of the *whole* share set — `media/` and `service/` come along
with them. `tmp/` is excluded: it is scratch, created by `storage/install_prep.sh` and written
by things like `benchmark.sh`'s fio test file, so replicating it costs space and preserves nothing. Two consequences, and the second is the awkward one:

- module backups reach cold **for free**, and are a rounding error beside the media on the same
  disk, which makes the sizing question in item 8 much less pressing than it looked
- **a mirror has no retention of its own**, so the sparse tail cannot live at cold. It lives at
  **warm** instead, and cold replicates the result. See *Retention, warm*

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

Blank in `.hosts` for a host with no share, in which case the key is omitted and the driver skips
the warm copy for that host. Declaring it rather than deriving it from position in `.hosts` is
deliberate: inserting a host would otherwise renumber every host after it and silently file backups
under another host's share. The driver therefore reads one source of truth — `config.json` — and
needs no `/etc/fstab` discovery.

## Module contract — built

A module holding state calls `write_container_backup()` in its generate script. That produces
`src/main/resources/backup.sh`, which lands at `${SERVICE_INSTALL}/backup.sh`
on the host, runs there, and writes into the module's own `${SERVICE_DATA_DIR}/backup/`.

**The call is the enrolment.** No call, no generated script, no participation — exactly as a module
without `write_container_healthchecks()` has no health checks. There is no `<MODULE>_BACKUP_ENABLED`
variable, because the presence of the call already says it. No registry, no list, and no way to be
half-enrolled, since the declaration is what produces the backup.

```python
write_container_backup()    # the whole enrolment, no policy parameters
```

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
<data dir>/backup/<stamp>/<module>_<stamp>_full.<extension>
<data dir>/backup/<stamp>/<module>_<stamp>_delta.<extension>
```

`<stamp>` is `%Y-%m-%d_%H-%M-%S` local, in both the directory and the filename. The **`_full` /
`_delta` suffix is the whole point**: it tells a later tier, without knowing anything about the
module, whether a backup stands alone.

- **`_full`** is self-contained. It can be kept as a sparse restore point and deleted individually.
- **`_delta`** depends on the full before it. It is only meaningful inside a window that also holds
  that full, and deleting a full invalidates every delta after it.

That is what makes GFS possible at warm without the driver learning anything module-specific: monthly
and weekly points must be `_full`, and `_delta` backups are only retained inside the dense window.
Modules producing standalone backups always emit `_full`; only `influxdb3` emits both.

### Kinds

Two kinds, named for what a single backup is worth on its own:

| Kind | Meaning |
|------|---------|
| `FULL` | self-contained backups only, each one restorable on its own |
| `DELTA` | dependent backups, a `_full` and the `_delta`s hanging off it |

| Module | Kind | Produced by | Backup |
|--------|------|-------------|----------|
| `postgres` | `FULL` | `pg_dumpall \| gzip` in the container | `postgres_<stamp>_full.sql.gz` |
| `mariadb` | `FULL` | `mariadb-dump --all-databases --single-transaction \| gzip` | `mariadb_<stamp>_full.sql.gz` |
| `zigbee2mqtt` | `FULL` | `zigbee/bridge/request/backup`, base64 zip off the response topic | `zigbee2mqtt_<stamp>_full.zip` |
| `letsencrypt` | `FULL` | `backup_files`, the shared `tar` of the paths it is passed | `letsencrypt_<stamp>_full.tar.gz` |
| `influxdb3` | `DELTA` | `influxdb3 create backup`, tarred out of the object store | `influxdb3_<stamp>_{full,delta}.tar.gz` |

A `FULL` backup is always self-contained, so any subset can be kept. A `DELTA`
module emits a `full` when there is none or the current one has aged past `BACKUP_RETAIN_DAYS`, and a
`delta` against the newest member otherwise.

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
| `BACKUP_INTERNAL_ROOT_DIR` | `${BACKUP_SOURCE_PATH}/backup` |
| `BACKUP_RUN_TIMESTAMP` | this run's timestamp |
| `BACKUP_FULL_SUFFIX` / `BACKUP_DELTA_SUFFIX` | the `_full` / `_delta` suffixes |
| `BACKUP_RETAIN_DAYS` | the dense window in days, default 7 |
| `BACKUP_SKIP_HOURS` | skip the run when the newest backup is younger than this, default 1 |
| `BACKUP_TARGET_PATH` | the backup path — empty until `backup_target` names it |

| Function | Purpose |
|----------|---------|
| `backup_target <suffix> <extension>` | name this run's backup, set `BACKUP_TARGET_PATH`, create its directory |
| `backup_epoch <name>` | timestamp to epoch |
| `backup_listed [dir]` | the stamp directories, oldest first |
| `backup_pruned [dir]` | delete past `BACKUP_RETAIN_DAYS`, always keeping the newest |
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

### It is sourceable, and that is how warm avoids knowing anything

The generated script ends its definitions with:

```bash
[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0
```

Executed, it takes a backup. **Sourced, it defines the module's vocabulary and returns**, so
supervisor's `backup.sh` can source a module's own `backup.sh` and get `BACKUP_FULL_SUFFIX`,
`BACKUP_DELTA_SUFFIX`, `backup_listed`, `backup_pruned` and the rest — for *that* module — without
supervisor containing a single module-specific line. Warm decides the policy; the module supplies
the vocabulary and the thinning.

Source each module in a subshell: the wrapper sources the module's `.env`, and five modules' worth
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
- write to a temporary name and rename on success, so warm never copies a half-written backup

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

### Retention, hot

`BACKUP_RETAIN_DAYS` is a guaranteed **minimum** recoverable window, not a footprint.

`FULL` modules delete backups older than the window, always keeping the newest
whatever its age, so a run of failures can never leave zero backups.

influxdb3 cannot be thinned that way. Restoring a delta walks back to the full it hangs off, and
deleting any backup cascades to everything depending on it, so the unit of retention is a full and
all its deltas. Two rules, same knob:

- **start a new full** when the current one is older than the window
- **delete a full and its deltas** only once the *next* full is older than the window, which is
  what keeps the window covered by a full predating it

A 7 day window therefore retains around 12 days and two fulls. Correct, not waste.

## Module inventory

Every module that runs a container, whether it holds state, whether it has a backup
script, and what to implement where it does not, is tabulated in **item 5 of *Gaps and
decisions*** — kept there rather than duplicated here, because for now it is a worklist
rather than a description of what exists.

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
5. **Wire nothing.** `supervisor` is the only invoker and finds the module by the generated script.
   Do not add an `install_pre.sh` or `install_prep.sh` — release-time triggering is retired.
6. **Do not add it to `src/resources.txt`.** The script reads its environment at runtime and holds
   no `${VAR}` placeholders.
7. **Check the result**: a successful run leaves exactly one backup named
   `<module>_<stamp>_full.<extension>`; a failed one leaves no file and no directory. Running it
   twice inside `BACKUP_SKIP_HOURS` must skip. Sourcing it must produce no backup.

## Driver — planned

**`supervisor` is the only thing that invokes a backup.** Release-time hooks are retired: the
backup call is removed from every `install_pre.sh` / `install_prep.sh`, and a hook left doing
nothing else is deleted outright.

| Hook | Action |
|------|--------|
| `mad/postgres/install_prep.sh` | delete — the backup call is all it does |
| `meg/mariadb/install_prep.sh` | delete — likewise |
| `max/influxdb3/install_prep.sh` | delete — likewise |
| `jen/zigbee2mqtt/install_prep.sh` | delete — likewise |
| `may/letsencrypt/install_pre.sh` | keep, drop the backup line — it still installs `pushcerts.service` |
| `all/storage/install_prep.sh`, `may/tempstat/install_prep.sh` | untouched, never referenced backup |

One trigger means backup cadence is a property of the schedule rather than of the deploy, which is
the point. The hooks were the old release-time mechanism and are simply gone; nothing depended on
them, so there is nothing to sequence around.

`supervisor`'s own generated `backup.sh` **is** the driver, and its snippet's `backup_written` is
the whole of it. The three tiers run serially, in order, for this host only: warm has nothing to copy
until hot has produced it, cold nothing to mirror until warm has been written and thinned.

Inputs, read from `.../supervisor/latest/image/config.json`, unless modules are named as arguments:

- `.asystem.host` → this host and its share index
- `.asystem.schema[] | select(.host == $host) | .services[]` → the modules

**hot** — for each module on this host, skipping `supervisor` itself, any with no
`backup.sh`, and any whose container is not running:

1. execute `${SERVICE_INSTALL}/backup.sh`, no arguments and no environment, it sources its
   own `.env`
2. exit `0` is produced or throttled by its own minimum interval, non-zero is failed, the rest of
   its output is log
3. it writes `${SERVICE_DATA_DIR}/backup/<stamp>/<module>_<stamp>_{full,delta}.<extension>`
4. never read a data directory, choose an exclusion or parse a backup — the module owns its
   format, its throttle and its pruning

**warm** — for each module whose hot run succeeded, so a bad backup is never promoted:

1. `rsync -a --link-dest` of the previous copy, no `--delete`, of
   `/home/asystem/<module>/latest/backup/` into `/share/<index>0/backup/<module>/`
2. source that module's `backup.sh` in a subshell, so `backup_is_full`, `backup_is_delta` and
   `backup_listed` are its own
3. thin to grandfather-father-son, oldest tier wins a tie:
   - **son** — every backup of either kind inside `BACKUP_RETAIN_DAYS`
   - **father** — the newest `_full` of each ISO week, for `BACKUP_KEEP_WEEKLY` weeks
   - **grandfather** — the first `_full` of each month, for `BACKUP_KEEP_MONTHLY` months
4. a `_full` stands alone, a `_delta` restores only with its `_full` and every `_delta` between, so
   father and grandfather are always `_full`, only son may hold a `_delta`, and a `_delta` whose
   `_full` has gone is dropped

**cold** — once, after warm, for each mounted share on this host rather than only the primary, both
sides guarded on `mountpoint`:

1. `rsync -a --delete --exclude backup/ --exclude tmp/` of `/share/<n>/` into `/backup/share/<n>/`,
   `tmp` being scratch never worth replicating
2. `rsync -a`, no `--delete`, of `/share/<n>/backup/` into `/backup/share/<n>/backup/`, so a
   mistaken thin at warm cannot reach the cold copy

**The backup is the run's log** — it exists only if the run completed, its timestamp says when,
and `BACKUP_RETAIN_DAYS` keeps a week of them. Status is read back with `backup_healthy` against
each module's own backup directory.

The three tiers are separable inside the one script, so they can be run or scheduled apart — hot
daily, warm immediately after, cold on its own slower cadence.

### How a module's script is executed

**One mode, always from the install directory:**

```
${SERVICE_INSTALL}/backup.sh
```

The script runs on the host and execs into its own container only if it needs something in there.
The driver never chooses between modes, never passes the script on stdin, and never needs a sidecar.

`${SERVICE_INSTALL}` is versioned and freshly copied each release, so the script that runs is always
the current one — which is what the `bash -s` stdin trick previously existed to guarantee.

`OFFLINE` stops being a driver concern and becomes ordinary module logic: a host-side script can
`docker stop`, copy, and `docker start` without dying, because it was never inside the container it
stopped.

### Resolving "a container cannot execute a host script"

**Mount the three directories the driver needs, at the paths they already have on the host.** Then
the script the driver runs is the same script, at the same path, reading and writing the same
places, whether it is invoked from a shell on the host or from inside `supervisor`:

| Mount | Mode | Why |
|-------|------|-----|
| `/var/lib/asystem/install` | `ro` | each module's `backup.sh` and its `.env` |
| `/home/asystem` | `rw` | the module data directories, where `backup/` is written |
| `/share` | `rw` | the warm destination |
| `/var/run/docker.sock` | `rw` | already mounted — `exec` into a module, and `stop`/`start` for offline copies |

Three consequences, all of them simplifications:

- **no prefix awareness.** A path is a path. Nothing has to know whether it is running in a
  container, and no `SUPERVISOR_MOUNT`-style rewriting is needed. `/` is currently mounted at
  `/host` read-only, which would have forced exactly that rewriting on every module script
- **nothing is spawned.** The driver executes the module's script directly. The throwaway
  container this document previously proposed is unnecessary and should not be built
- **`OFFLINE` stops being special.** A script running inside `supervisor`'s container can
  `docker stop` a *different* container without dying, so stop-copy-start needs no sidecar, no
  separate execution mode, and no driver involvement

Only two prerequisites remain: a docker client in the image (`docker_deps_base.txt` has none), and
these mounts replacing the current read-only `/:/host`.

### Copy rules

**hot to warm is additive** — `rsync -a` without `--delete` — in both shapes. Mirroring here would
propagate the hot tier's seven day window to warm, and no history longer than a week could exist
anywhere. `--link-dest` against the previous copy makes an unchanged backup cost an inode rather
than its bytes.

**warm thins, then cold mirrors.** The driver copies from hot, applies the GFS policy to what it
holds, then replicates the share to `/backup`. Warm is the only tier that
deletes a backup on purpose.

**cold covers every share, not just the one warm writes to.** Warm only ever touches
`/share/<index>0/backup/`, but cold replicates `/share/*` into `/backup/share/*`, so the media and
data on a host's other shares are carried by the same job.

**`--delete` everywhere except `backup/`, and that choice decides where retention actually bites.**
Warm is the only tier that deletes a backup on purpose — the GFS thin. Cold then has to decide
whether to copy that decision:

| Cold path | `--delete` | Consequence |
|---|---|---|
| `media/`, `service/` | **yes** | a file deleted on the share disappears from cold, which is what a mirror is for |
| `tmp/` | — | not replicated at all; scratch, and large enough to be worth skipping |
| `backup/` | **no** | cold keeps every backup warm ever held, including ones warm has since thinned |

So **the GFS policy bounds warm, not cold**. Cold is append-only for backups and grows by the thin
churn — a full and its deltas per week, a full per month — which at these volumes is small beside
the media on the same disk. What it buys is that a mistaken or buggy thin at warm cannot reach the
only remaining copy: the two tiers can never be wrong in the same way at the same time.

The alternative is `--delete` on `backup/` too, making cold an exact mirror and bounding both tiers
by the same policy. That is tidier and cheaper, and it is the right change if cold ever grows
uncomfortably — but it removes the second copy's independence, so a single bad prune at warm would
take both. Not worth it while the backups are this small.

Either way, **nothing at cold prunes on its own**. If `backup/` is append-only it needs an eventual
ceiling, and that ceiling is the only retention this document does not yet specify.

**Guard on `mountpoint` before writing.** The shares are automounts; writing to an unmounted
`/share/10` silently creates the path on the root filesystem and fills the OS disk.

## Boundary with Go — planned

Go is **only the scheduler**. The script must stay runnable by hand with no supervisor process.

| | Owns | Must not |
|---|---|---|
| `backup.sh` (supervisor's) | discovering modules, running them, the `/share` copy, skip and retention decisions, locking, writing the result | publish MQTT, write InfluxDB, daemonise, schedule |
| Go | when to run, a wall-clock ceiling on a run, reading the result, judging staleness, publishing `Backup Status` | build the module list, exec a module itself, know `/share` paths or any backup format |

If Go ever does something in its right-hand column, the script has stopped being independent. That
is the test to apply to any change here.

**Exit codes** let a scheduler tell two different alarms apart:

| | |
|---|---|
| `0` | every selected module backed up or legitimately skipped |
| `1` | at least one module failed — partial |
| `2` | could not start — no config, share not mounted, lock held |

**The filesystem is the result — there is no report file.** A backup's *existence* means that
backup succeeded, because nothing is renamed into place until it did; its *timestamp* says when. So
everything a report would have carried is already on disk, and a second source of truth that could
disagree with it is not worth having.

`backup_healthy` in the wrapper reads exactly that:

```bash
BACKUP_ELAPSED="3600"
BACKUP_MAX_AGE=$((86400 + BACKUP_ELAPSED))
```

A module is healthy when its newest backup is younger than `BACKUP_MAX_AGE` — a daily cadence plus
an hour's allowance to get through every module, so **25 hours**. The allowance is a variable rather
than a literal 25, so the arithmetic stays legible and either half can move.

Go therefore needs no new file format and no parsing: for each module, source that module's
`backup.sh` in a subshell and call `backup_healthy`, or apply the same rule to
`/home/asystem/<module>/latest/backup/` directly. It reads the *current* state rather than the last
run's claim about it, so a manual run, a partial run, or a supervisor restart all give the same
answer — and there is no report to go stale.

**A lock belongs in the script** — `flock`, exit `2` if held — so a scheduled run and a hand run
cannot collide. Together with `BACKUP_SKIP_HOURS` that is what makes running it yourself always safe.

**The timeout removed from the influxdb3 script reappears here, correctly.** `backup_awaited` now
waits forever, which would hang Go's exec. A scheduler is the right owner of "this
run has taken too long": Go applies a deadline and kills the script. Nothing corrupts — the
server-side backup continues and the next run's status poll finds it. Waiting is the script's job;
giving up is the scheduler's.

**Staleness is Go's judgement.** The script reports facts; Go decides that no `ok` in 36 hours means
unhealthy and flips `backupStatus()`.

One tradeoff, accepted: a systemd timer would survive supervisor being down, whereas in-supervisor
scheduling makes the scheduler a dependency of the backup. Against that, supervisor is already the
per-host agent that knows the config and owns the metric.

## Generation — built

### Why generate

Measured before building it: `postgres` and `mariadb` differed by **four lines** once the module
prefix and the dump command were normalised, and the listing/epoch/prune helper block was
**byte-identical** between `postgres` and `letsencrypt`. Of 78 lines, roughly 70 were boilerplate —
and they were precisely the lines carrying the hazards: implicit self-exclusion, atomic rename,
metadata preservation, keeping the newest backup regardless of age, sweeping stale `.tmp`, and not
pruning after a failure. Generating them fixes each hazard once instead of once per module.

The five snippets that replaced those scripts total **under 90 lines**, of which `influxdb3` is 63.

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
- `letsencrypt` defines `backup_written` as a call to `backup_files` with its paths
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

A `.sha256` sidecar was considered and rejected: every backup is `.gz` or `.zip`, whose container
formats already carry CRC32, so `gzip -t` detects corruption without a second file to keep in step.
If periodic integrity checking is ever wanted, that is the mechanism, not a sidecar.

### Classifying a backup

```bash
backup_is_full() { [[ "${1}" == *"${BACKUP_FULL_SUFFIX}".* ]]; }
backup_is_delta() { [[ "${1}" == *"${BACKUP_DELTA_SUFFIX}".* ]]; }
```

These are what let the warm step apply GFS to a module it knows nothing about: a `_full` may be kept
as a weekly or monthly point, a `_delta` only inside the dense window.

## Restore

| Module | Procedure |
|--------|-----------|
| `influxdb3` | untar the `_full` and every `_delta` after it, in order, into an empty object store — a `_delta` is meaningless without the `_full` it hangs off |
| `postgres` | `gunzip -c all_<stamp>.sql.gz \| psql -U postgres` |
| `mariadb` | `gunzip -c all_<stamp>.sql.gz \| mariadb -uroot -p` |
| file copy | restore the backup over the data directory, then redeploy the module so the git-managed files return |

For anything older than the hot tier, restoring in place is rarely right — rolling a database back
a month discards a month of good data. Stand the copy up beside production, compare, and extract the
range that matters.

HA's configuration lives in `homeassistant` but its recorder lives in `postgres`, so restoring HA to
a day needs both at that day. A single daily pass produces same-day backups minutes apart: not
transactional, but a loose estate-wide restore point, and a reason to keep every module on one
schedule rather than letting them drift onto their own.

## Retention, warm — planned

**The sparse tail lives at warm, because cold is a mirror and a mirror cannot thin.** Whole-share
replication copies what it finds; it cannot also be the thing that keeps twelve monthly points and
discards the rest. So warm owns the policy and cold replicates the outcome.

**The volumes are not all alike, and this is what the full/delta design is about.** The SQL dumps,
the zigbee coordinator backup and the letsencrypt tar are small and stay small — a full copy of each
at every retention point costs nothing. InfluxDB is the opposite: it accumulates continuously and
will grow without bound, which is precisely why it takes incremental backups instead of full ones.

That creates a tension the sparse tail has to answer for, because **a sparse restore point must be
self-contained, and for a `DELTA` module that means a `_full` — a complete copy.** Daily deltas are cheap;
twelve monthly points are twelve full copies of a growing store. GFS at the monthly tier therefore
reintroduces exactly the cost deltas exist to avoid, for the one module where it hurts.

Three ways to answer it, and the right one depends on growth rather than on today's size:

- **shorter monthly depth for InfluxDB than for everything else** — the retention knobs should be
  overridable per module (`<MODULE>_BACKUP_KEEP_MONTHLY` and friends) rather than one estate-wide
  policy, which the env-driven convention already supports
- **longer runs between fulls** — one full and many deltas, so the tail is cheap, at the cost of a slower
  restore and a larger blast radius if a link is corrupt
- **deduplication** — a `restic`/`borg` repository fed from warm, which is where its value actually
  lies, since it makes twelve monthly fulls cost close to one

That third option was rejected above on the grounds that volumes are small. **That reasoning holds
for four of the five modules and expires for InfluxDB**, so the decision is *not yet*, not *no* —
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
the filename suffix declares, and why warm can apply this policy without knowing which module it is
looking at. Deltas are only ever retained inside the dense window.

**Warm must not thin blindly**, and the `_full` / `_delta` suffix is what stops it having to guess.
Dropping a `_full` destroys every `_delta` after it, so warm keeps `_full` backups as its weekly
and monthly points and retains `_delta` backups only inside the dense window.

**So warm delegates: it calls the module's own `backup.sh --prune <dir>` against the warm
directory.** Warm decides the policy — which points to keep, from the GFS knobs in the environment —
and the module enacts it on backups it alone understands. A `FULL` module reuses its
default pruning against a different directory; `influxdb3` applies its own rule. No new script and
no new hook, and the driver never learns which module it is thinning.

It also falls out of the hot design for free, because pruning was already an overridable step; the
only change is that it takes the directory to work on rather than assuming its own.

## Gaps and decisions

Nine items. **Open** means an answer is still needed from a human; **gap** means something is missing
or wrong with no question attached. Ordered by what would hurt most.

This is day 0 for backups — the hot tier is built and nothing precedes it, so nothing here is a
regression or a race. It is a build order.

| # | Item | State | Blocks |
|---|------|-------|--------|
| 1 | No restore has ever been tested | gap | trusting any of this |
| 2 | influxdb3 keeps two copies and prunes neither | **defect** | running daily |
| 3 | The driver is not built — supervisor's snippet is still a TODO stub | gap | daily backups, warm, cold |
| 4 | Warm would publish secrets on a public samba share | **open** | warm |
| 5 | Cold does not exist, and has no ceiling of its own | gap, decided | off-host |
| 6 | Six modules need a script, four need a verdict | gap, partly **open** | knowing this is sufficient |
| 7 | Nothing reports backup health | gap | — |
| 8 | Nothing has been sized | gap | cold sizing |
| 9 | No automated tests | gap | — |
| 10 | Detection latency dominates retention depth | gap | — |
| 11 | A module's script has no lock | gap, minor | — |

One question is genuinely waiting on you: **4**, which samba fix. Everything else is work, not a
question.

Out of scope, deliberately: media and user data on `/share/<n>/{media,service}`, which is not
module state — though it shares the `/backup` disk and the cold job, so it is out of scope for
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
  `${{SERVICE_DATA_DIR}}/cluster_1/backups/` accumulates every full and delta ever taken, for ever.
  The wrapper's `backup_pruned` only reaps `backup/<stamp>` directories — our tars — and never
  touches what the server holds.
- **every backup exists twice on disk**, once as the server's directory and once as our gzipped tar.
  The hand-written version avoided this with a hardlinked export that cost nothing.

Both land on the one module that actually grows, which is the worst place for them. The fix is a
handful of lines in the snippet: after a successful tar, delete the server-side backup whose contents
were just captured, keeping only what a restore needs — and honouring the cascade, since deleting a
full removes its deltas. Must be fixed before anything runs this daily.

### 3 The driver is not built — gap

Every module's `backup.sh` works and can be run by hand; nothing calls them on a schedule yet, and
warm and cold do not exist.

`supervisor` is enrolled through `write_container_backup()` like any other module, and its snippet
**is** the driver: `backup_written` runs hot, warm and cold **serially** — warm has nothing to copy
until hot has produced it, and cold has nothing to mirror until warm has been written and thinned.
The snippet exists as a pointer to that section and a `return 1` placeholder, so the script is
generated, lints, and fails honestly rather than pretending to work.

Enrolling it this way is what gives the driver the shared vocabulary — `BACKUP_FULL_SUFFIX`,
`BACKUP_DELTA_SUFFIX`, `backup_is_full`, `backup_listed`, `backup_pruned`, `backup_healthy` — without a
second implementation of any of it, and it makes the wrapper's own behaviour correct for a driver
rather than merely tolerated: the throttle stops a second estate-wide run within the hour, the
`.tmp`-and-rename means a killed run leaves no trace, and `backup_pruned` keeps a week of runs.

**Its backup is the run log** (`backup_target "${BACKUP_FULL_SUFFIX}" "log"`), so
`supervisor_<stamp>_full.log` exists
only if the run completed, and its timestamp says when. That is the same filesystem-as-state rule
every module follows, applied to the run itself.

Two prerequisites remain either way: a docker client in the image (`docker_deps_base.txt` has none)
and the three same-path mounts replacing the read-only `/:/host`.

A per-host cron calling each `${SERVICE_INSTALL}/backup.sh` is a reasonable interim if daily
hot backups are wanted before the driver lands — it needs nothing that does not already exist.

### 4 Warm would publish secrets on a public samba share — open, blocks warm

`storage/install_prep.sh` publishes every `/share/<n>` as `public = yes`, `read only = no`,
`create mask = 0666`. The moment the `/share` copy starts, database dumps — and HA's `secrets.yaml`
and `.storage/auth` when that module gains a script — are readable by anything on the LAN reaching
samba. They cannot be excluded, because a restore needs exactly those files. Pick one:

- move `backup` outside the published tree, a sibling of `/share/<n>` rather than a child
- give `backup` its own restricted share, overriding the per-share block

### 5 Cold does not exist — gap, design decided

Everything lives on the machine it protects, so a dead host loses hot and warm together.

The shape is settled: cold is the replication of `/share` to `/backup`, module backups riding
along in the `backup/` subtree, and **warm owns the GFS thinning** because a mirror cannot thin. A
`restic`/`borg` repository alongside it was considered and rejected at these volumes — revisit only
if the volumes ever justify it. Nothing new has to own cold: whatever replicates `/share`
to `/backup` does the job, with `backup/` excluded from `--delete` so a mistaken thin at warm cannot
reach both copies.

What is left is building the warm and cold halves of supervisor's `backup.sh`. The thinning question is settled:
the `_full` / `_delta` suffix tells warm what is safe to drop, and warm can source a module's
`backup.sh` for its vocabulary or call it with `--prune <dir>`.

Until then, **warm has no retention at all** — the copy from hot is deliberately additive, so
nothing on the share is ever deleted.

And once built, **cold still has no ceiling of its own**. `backup/` is deliberately excluded from
`--delete` so a bad thin at warm cannot reach both copies, which means cold accumulates every
backup warm ever held. Affordable at current volumes, and the last retention this document does
not specify — see *Copy rules* for the trade and the alternative.

### 6 Six modules need a script, four need a verdict — gap, partly open

Every module that runs a container, whether it holds state and what to do about it. **Required** is a
proposal from reading mounts, run-dependencies and shipped data, not a finding — confirm each before
acting. The 29 remaining directories under `src/` have no `docker-compose.yml` at all: they are host
configuration and tooling, with no container and no service state.

| Module | Host | Backup | Required | Suggested implementation |
|--------|------|--------|----------|--------------------------|
| `influxdb3` | max | ✅ `DELTA` | — | snippet defines `backup_written` and adds full/delta helpers |
| `postgres` | mad | ✅ `FULL` | — | `docker exec postgres bash -c 'pg_dumpall -U postgres \| gzip' >"$1"` |
| `mariadb` | meg | ✅ `FULL` | — | `docker exec mariadb bash -c 'mariadb-dump --all-databases --single-transaction \| gzip' >"$1"` |
| `zigbee2mqtt` | jen | ✅ `FULL` | — | MQTT bridge request, base64 zip off the response topic |
| `letsencrypt` | may | ✅ `FULL` | — | `backup_written` calling `backup_files` with its paths |
| `homeassistant` | meg | ❌ | **yes** | prefer its backup integration — POST to the API with the `HOMEASSISTANT_API_TOKEN` already in its environment, then collect the tar it writes. Fallback: `INCLUDE=.storage` with `OFFLINE`. Note its native path is `/config/backups`, one letter from ours |
| `plex` | mad | ❌ | **yes** | library database is live SQLite — `docker exec plex sqlite3 <db> ".backup $1"` if `sqlite3` can be added, else `OFFLINE` with `backup_files` of `Preferences.xml` and `Plug-in Support/Databases`. Exclude `Metadata/` and `Cache/`, which are large and regenerable |
| `sonarr` | may | ❌ | **yes** | `sonarr.db` and `config.xml`. Sonarr's v3 API is believed to expose a Backup command — verify before relying on it; otherwise `OFFLINE` with `backup_files` |
| `sabnzbd` | mad | ❌ | **yes** | `sabnzbd.ini` and `admin/` (history and queue databases, written live) — `OFFLINE` with `backup_files` |
| `grafana` | may | ❌ | **yes** | users, API keys and preferences in `grafana.db`; dashboards come from jsonnet so are not needed. `sqlite3 grafana.db ".backup $1"` is online-safe, else `OFFLINE` with `backup_files` |
| `mlflow` | max | ❌ | **yes** | **not visible in a data-directory scan** — its backup root is a share mount, `/share/1/service/mlflow/backups` in production. Experiment metadata is in `postgres` and already covered; the backups are not. A tar of the backup root, or a deliberate decision that backups are reproducible |
| `rhasspy` | zzz | ❌ | verify | trained voice profiles, if any are trained — `backup_files` the profile directory, else declare derived |
| `openra` | max | ❌ | verify | settings and replays; low value, most likely declare derived |
| `appdaemon` | zzz | ❌ | verify | apps come from git — check whether anything generated is kept alongside them |
| `vernemq` | meg | ❌ | verify | retained messages, but each module's `vernemq.sh` republishes its own on deploy, so most likely derived. If not, dump retained topics with `mosquitto_sub` |
| `weewx` | jen | ❌ | no | writes to the `mariadb` weewx database; configuration and skins from git |
| `wrangle` | mad | ❌ | no | writes to `postgres` |
| `network` | mad | ❌ | no | writes to `influxdb3` and MQTT |
| `tempstat` | may | ❌ | no | writes to MQTT |
| `nginx` | meg | ❌ | no | configuration generated, certificates pulled from `letsencrypt` |
| `cloudflare` | may | ❌ | no | configuration generated, credentials from the environment |
| `supervisor` | all | ❌ | no | data directory holds the binary, shipped each release |
| `mlserver` | max | ❌ | no | mounts `mlflow`'s backup root; no state of its own |
| `monitor` | zzz | ❌ | no | host paths mounted read-only |
| `unpoller` | zzz | ❌ | no | no volumes |
| `redpanda` | zzz | ❌ | no | no volumes |

Two things this table changed. **`mlflow` was missed** by the original inventory because it holds no
`${SERVICE_DATA_DIR}` — presence of a data directory is not the same as holding state, and any
future module mounting a share needs the same second look. And **`homeassistant` is the last open
mechanism question**, now that `zigbee2mqtt` has settled the pattern for a module with a native API.

Order of work, once confirmed: `homeassistant` (largest irreplaceable state), then `mlflow`
(silently uncovered today), then `sonarr`, `sabnzbd`, `plex`, `grafana` — all four of which are the
same `OFFLINE` file-copy shape and can share one snippet pattern.

### 7 Nothing reports backup health — gap

`backupStatus()` is a stub returning `true` (`internal/probe/probe_services.go`), so a persistently
failing backup is visible only in a log, even though a `Backup Status` measure and a Home Assistant
entity already exist for it. Wire it to `backup_healthy`, per module — the rule and the threshold
already exist in every generated script, so this is a call site, not a design.

### 8 Nothing has been sized — gap

Partly answered by the cold-tier finding: module backups share the `/backup` disk with the media,
which dwarfs them, so *will it fit* is no longer the worry it looked. What is still unmeasured is the
influxdb3 object store, the dump sizes, and what the per-release `cp -rfpa` of the backup tree costs
at the current cadence. Two commands settle it:

```bash
du -sh /home/asystem/*/latest/backup
du -sh --count-links /home/asystem/influxdb3/latest/cluster_1/backups   # vs without
```

The second also answers whether influxdb3 fulls share storage, which decides how many sparse
restore points are affordable.

### 9 No automated tests — gap

The scripts have been exercised by hand against stubbed CLIs in a container, but nothing runs in
`fab ut` or `fab st`. The full/delta logic in particular — when to start a new full, and the rule
that keeps a full predating the window — is the kind of thing that breaks silently on a later edit.

### 10 Detection latency dominates retention depth — gap

A year of monthly copies only helps if the damage is eventually noticed. Scheduling `describe.sh`
and diffing its output would shorten time-to-notice far more cheaply than lengthening the tail, and
supervisor is about to be the scheduler anyway.

### 11 A module's script has no lock — gap, minor

Two concurrent runs of the same module's `backup.sh` inside one second would share a stamp and race
on the same `.tmp`. The `BACKUP_SKIP_HOURS` throttle makes it unlikely rather than impossible, and the
driver is expected to hold a lock of its own, but a `flock` on `BACKUP_INTERNAL_ROOT_DIR` would close it properly.

### Closed during design and build

- **Encryption at rest** — decided against. Backups stay in the clear at every tier. That also
  removes the one argument that would have justified `restic`/`borg` at current volumes, so cold
  stays a plain mirror, and it narrows item 3 to two options rather than three.

- **Generation** — `write_container_backup()` is built, all five modules go through it, and the
  wrapper/snippet split is proven. No module is exempt, so no script exists that generation would
  not recreate.
- **Always run from the install directory** — one execution mode, no sidecar, no `bash -s`.
- **Per-module env vars** — `<MODULE>_BACKUP_ENABLED` / `_MIN_INTERVAL` / `_RETAIN_DAYS` /
  `_INCLUDE` / `_OFFLINE` / `_TIMEOUT` are all gone. Presence of the generate call is the enable;
  the two policy values are overridable wrapper variables; everything else is a snippet variable.
- **`full` / `delta` naming** — one vocabulary from the backup filename down to influxdb3's
  server-side backup names, its snippet's `backup_stored` / `INFLUXDB3_BACKUP_STORE`, and its log
  lines. `base`, `inc` and `chain` are retired, in the code as well as the prose.
- **Dependency-aware thinning** — the `_full` / `_delta` suffix plus `backup_is_full` /
  `backup_is_delta` let warm apply GFS to a module it knows nothing about.
- **Share index** — the sixth field of `.hosts`, read by `_get_host_index()`, emitted into
  `config.json`.
- **How a container runs a host script** — same-path bind mounts; the sidecar proposal is withdrawn.
- **`OFFLINE` execution mode** — no longer a driver concern; a script in supervisor's container can
  stop a different container without dying.
- **`zigbee2mqtt` mechanism** — its bridge API over MQTT.
- **A `.sha256` sidecar** — rejected; every backup is `.gz` or `.zip`, whose formats already carry
  CRC32, so `gzip -t` detects corruption without a second file to keep in step.
- **influxdb3 excluding unpersisted data** — accepted, not fixed. A backup covers only what has
  reached object storage, so with `INFLUXDB3_GEN1_DURATION=10m` its restore point lags the SQL
  modules by up to the gen1 window. Inferred from the documented behaviour, not measured.
- **The dangling Time Machine reference** in `storage/install_prep.sh` names
  `${SHARE_DIR}/backup/timemachine`, which is no longer created; the block is disabled, so this is
  noted rather than open.
