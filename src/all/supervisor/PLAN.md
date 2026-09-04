# Backup

How every stateful module is backed up, where the copies live, how long they are kept, and how to
restore. Status is marked per section: **built** is in the repo today, **planned** is not.

**How to read it.** *Stages* is the shape of the whole thing and is the only section that has to be
read first. After that the document runs design, then implementation, then what is missing:

| | Sections |
|---|---|
| **what a backup is** | *Stages*, *Module contract*, *Adding a backup script* |
| **what runs it** | *Driver* — the daily gate, the singleton, the stage scripts, the broker namespace, the metrics |
| **what is kept, where, and for how long** | *Copy rules*, *Retention, secondary stage*, *Filesystem, tertiary stage* |
| **how it is built and restored** | *Boundary with Go*, *Code style*, *Generation*, *Restore* |
| **what is not done** | *Gaps and decisions*, sixteen numbered items and a closed list |

**It is one document on purpose.** Built and planned sit together rather than the built half moving
into the module `CLAUDE.md`, because the value here is the design read end to end — why a stage is
shaped the way it is, and what was tried and rejected — and a reader following that should never
have to jump files. The **built** / **planned** markers carry the distinction instead. Revisit only
if the planned half is ever finished, at which point this becomes a record rather than a plan.

Three vocabularies carry most of the meaning and are each defined once. The three **stages** are
`primary` / `secondary` / `tertiary`, named for how far a copy has travelled from what it protects
(*Stages*). The **portable timestamp** is `%Y-%m-%d_%H-%M-%S`, the traceable identifier that joins a
run across hosts, logs, snapshots and payloads (*Backup naming*), and is distinct from an RFC 3339
instant, which measures a moment. **Module** and **service** are not synonyms: a *module* is what is
in source control and ships the `backup.sh` snippet, a *service* is the container running it on a
host. Enrolment is a property of the module; everything a run produces — the topic level, the run
directory entry, the log file, the status document — is named for the service.

## Stages

**A backup run is three stages, and `stage` is the only word for one.** `hot`, `warm` and `cold`
are retired, and so is the destination-naming that replaced them — in the prose, in the status
document, in the log file names and in the Go. Each stage is named for **how far the copy has
travelled from the thing it protects**, so the ordering is in the name and a stage cannot be
confused with the `/share` or `/backup` disk it happens to write to, nor with the repo *module*
whose data it carries:

| Stage | Writes to | Protects against | Retention | Runs on | Status |
|-------|-----------|------------------|-----------|---------|--------|
| **primary** | `/home/asystem/<service>/backup/<timestamp>/` | a bad release, an accidental delete, logical corruption | dense — 7 days | every `edge` and `server` host | **built** |
| **secondary** | `/share/<index>0/backup/<service>/` | loss of the service data directory or its filesystem | sparse — GFS, daily 7 / weekly 4 / monthly 12 | every `edge` and `server` host | **planned** |
| **tertiary** | `/backup/share/<index>0/backup/<service>/` | loss of the host or its principal share | exact mirror of share, `--delete` throughout | `server` hosts only | **planned** |

**Which stages a host runs is its `.hosts` form-factor and nothing else.** The fifth field of
`.hosts` (`network|client|edge|server|ignore`) already decides which hosts get a `config.json`
schema entry — `generate.py` emits one only for `edge` and `server` — and it now also decides how
far a host carries a backup:

| Form-factor | `config.json` schema entry | primary | secondary | tertiary | owns `/backup` | in the power-off election |
|---|---|---|---|---|---|---|
| `server` (`mad`, `max`, `may`, `meg`) | yes, with `index` and a `backup` block | yes | yes → its own `/share/<index>0` | **yes**, every mounted `/share/*` | yes | yes |
| `edge` (`jen`, `jil`) | yes, no `index`, no `backup` block | yes | yes → a `server`'s principal share, already fstab-mounted | **no** | no | no |
| `client` / `network` / `ignore` | none | — | — | — | — | — |

A host with no schema entry has no configured services and no `backup` block, so `probe_impl_backup.go`
finds nothing to do — the same way `MetricHostAllocatedMemory` reads not-ok on a host absent from
the schema. Whether such a host runs `serve` or `watch` is unchanged by any of this.

An `edge` host is a satellite: it produces its module backups and pushes them onto a `server`'s
share, and the `server` that owns that share carries them the rest of the way. It never powers the
backup disk, never mounts `/backup`, and runs no tertiary stage. A `server` owns disks and runs the
full replication. Nothing in the Go names a host — the probe reads the form-factor through
`config.json` the way it reads everything else, and the boundary test in *Boundary with Go* is
unchanged.

**Only the tertiary stage waits on a powered disk.** `/share/<n>` holds live data — Plex's media
library, each service's `service/` tree — so it is always mounted and always spinning; a host writes
its secondary stage into it with no power step and no `mount.sh`. `/backup` is the cold mirror: a USB
spinning drive on a switched outlet, powered off between runs, mounted by `server` hosts only, and
the reason the tertiary stage begins by turning that outlet on and waiting for the disk to
enumerate. See *Powering and mounting the backup disks*.

A copy is only worth what it survives. Each stage protects against the failure the one before it
cannot, and each is thinner than the last — the retention goes from **dense** (every backup, a week
deep) to **sparse** (a year deep, a handful of points), because the further back you look the less
resolution is worth paying for.

**The secondary stage is not off the host.** `/share/<n>` is a local ext4 partition
(`PARTLABEL=share_08 /share/10 ext4 …`) on a `server`, so a `server` that dies takes the primary and
secondary stages with it. The secondary stage exists to get copies off the service data directory
and onto a large disk a later process can pull from. Only the tertiary stage is a real backup.

**For an `edge` host the secondary stage is already off the host.** `jen` has no share of its own, so
its `/share/10` is `mad`'s partition reached over samba (an fstab `cifs` entry, mounted
automatically). `jen`'s secondary stage writes its module backups straight into `mad`'s
`/share/10/backup/<service>/`, and `mad`'s tertiary stage — replicating **every** mounted `/share/*`,
not only its principal one — mirrors that subtree to `/backup/share/10/backup/<service>/` for free.
`jen` never learns the backup disk exists.

**The tertiary stage is a subtree of a share replication, not a backup-specific job.** `/backup` is a
separate mounted disk that mirrors `/share`, and the stage replicates **every** mounted share on the
host — `/share/*` into `/backup/share/` — not only the principal one.
`/backup/share/<index>0/backup/<service>` is simply where the service backups land inside a copy of
the *whole* share set — `media/` and `service/` come along with them. `tmp/` is excluded: it is
scratch, created by `storage/install_prep.sh` and written by things like `benchmark.sh`'s fio test
file, so replicating it costs space and preserves nothing. Two consequences, and the second is the
awkward one:

- module backups reach the tertiary stage **for free**, and are a rounding error beside the media on
  the same disk, which makes the sizing question in item 8 much less pressing than it looked
- **a mirror has no retention of its own**, so the sparse tail cannot live at the tertiary stage. It
  lives at the **share** stage instead, and the tertiary stage replicates the result. See
  *Retention, secondary stage*

`/share/<n>` mounts are numbered *host* then *drive* — mad `10 11 12`, max `20 21`, may `30 31 32`,
meg `40` — so `<index>0` is the host's **principal share**, and `principal` is the word for it
throughout — `primary` now names a stage and nothing else.

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

**A host with no index is an `edge` host, and it borrows a share rather than owning one.** `jen`
holds real state (`zigbee2mqtt`'s coordinator database) and must reach the secondary stage like any
other host, so it writes into another host's share over samba. It does **not** reach the tertiary
stage itself — the `server` that owns the borrowed share does that on `jen`'s behalf. The index
therefore names the *preferred* principal share for a `server` that has one, and **fstab is the
authority for an `edge` host that does not** — the share destination is the lowest-numbered
`/share/<n>` actually mounted, which on `jen` is `mad`'s `/share/10`. That is the one place
`/etc/fstab` is read rather than `config.json`, and it is read by the secondary stage's own script
rather than by the probe. An `edge` host's fstab share is a plain `cifs` entry, mounted
automatically and always available, so no `mount.sh` and no power step is involved for it. See
*Powering and mounting the backup disks*.

## Module contract — built

A module holding state calls `write_container_backup()` in its generate script. That produces
`src/main/resources/backup.sh`, which lands at `${SERVICE_INSTALL}/backup.sh` on the host, runs
there, and writes into the module's own backup root. **That script is the primary stage and nothing
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
already performing in Go. Its own state needs no script either: the run record the driver writes
every day *is* its backup, sitting in the standard backup root as described under *The run's
output*, so the secondary and tertiary stages promote it as they find it. Six modules are
enrolled today — `postgres`, `mariadb`, `influxdb3`, `zigbee2mqtt`, `letsencrypt`, `plex`.

**The call takes no policy.** It resolves `module_name` / `working_dir` the standard way and nothing
else — the two policy values are wrapper variables with defaults, `BACKUP_RETAIN_DAYS` (7) and
`BACKUP_SKIP_HOURS` (1), each written as `${VAR:-default}` **after** the module's `.env` is
sourced. So a module changes them in its env files, and an operator overrides them per run:

```bash
BACKUP_SKIP_HOURS=0 ./backup.sh    # take one now, whatever the last run's age
```

A generate parameter could do neither of those, which is why they are variables.

**The throttle is version-qualified, and that qualifier is load-bearing.** `BACKUP_SOURCE_VERSION` is
the basename of the resolved data path, so it changes the moment the home moves to a new version, and
the wrapper skips only when the newest backup is *both* inside the window and from that same version.
The rule it expresses is **never skip the first backup of a version's data**: the day after a release
the daily run finds a backup taken minutes ago at release time — of the *old* home — and takes
another one anyway, because what is being protected is now different data. Dropping the qualifier
would make the wording simpler and the behaviour wrong, suppressing the new version's first backup
for a day.

### Backup naming

```
<data root>/backup/<timestamp>/<service>_<timestamp>_<version>_full.<extension>
<data root>/backup/<timestamp>/<service>_<timestamp>_<version>_delta.<extension>
```

`<data root>` is the **parent** of the data directory, so backups sit beside the versioned homes
rather than inside one — `/home/asystem/<service>/backup`, not `/home/asystem/<service>/<version>/backup`.
That keeps them clear of `install.sh`, which copies the old home into the new one on every deploy and
prunes the older homes; a backup directory inside a home was duplicated forward by that copy.

**`<timestamp>` is `%Y-%m-%d_%H-%M-%S` local, and this document calls it the *portable
timestamp*.** It is one format with one job: to be **traceable**, meaning byte-identical wherever it
appears so that a night's work joins by plain string equality and never by a time comparison. It is
the directory name, the filename segment, the btrfs snapshot label and the value of the `run_id`
field in every broker payload, which is the key that ties all of them together — see *Stage scripts
and the broker namespace*. Being sortable lexicographically, filesystem-safe on every path it lands in, and free of
the `:` the log conventions forbid are all consequences of the same choice.

It carries **no zone and no offset**, and that is deliberate rather than an oversight. An identifier
that has to match exactly cannot also be normalised, and portability here means *across the hosts of
this estate*, all of which take one `TZ` from `.env_all` — Perth, which has no DST, so two hosts
producing the same instant produce the same string. It is **not** an instant to do arithmetic on:
where a moment is measured rather than named, the field is an RFC 3339 instant with its offset (see
*The run's output*), and the two are never interchanged.

The directory name is the bare portable timestamp and nothing else — `backup_listed` matches it with
an anchored pattern, so anything appended there would hide the backup from listing, pruning and the
health check.

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

That is what makes GFS possible at the secondary stage without the driver learning anything
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
| `postgres` | `FULL` | `pg_dumpall \| gzip` in the container | `postgres_<timestamp>_<version>_full.sql.gz` |
| `mariadb` | `FULL` | `mariadb-dump --all-databases --single-transaction \| gzip` | `mariadb_<timestamp>_<version>_full.sql.gz` |
| `zigbee2mqtt` | `FULL` | `zigbee/bridge/request/backup`, base64 zip off the response topic | `zigbee2mqtt_<timestamp>_<version>_full.zip` |
| `letsencrypt` | `FULL` | `backup_files`, the shared `tar` of the paths it is passed | `letsencrypt_<timestamp>_<version>_full.tar.gz` |
| `plex` | `FULL` | `backup_files` with the service stopped | `plex_<timestamp>_<version>_full.tar.gz` |
| `influxdb3` | `DELTA` | `influxdb3 create backup`, tarred out of the object store | `influxdb3_<timestamp>_<version>_{full,delta}.tar.gz` |

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
| `BACKUP_SKIP_HOURS` | skip the run when the newest backup is younger than this **and came from the same version**, default 1 |
| `BACKUP_SERVICE_RESTART` | start the service again after the copy, false when the caller starts it itself |
| `BACKUP_TARGET_PATH` | the backup path — empty until `backup_target` names it |

| Function | Purpose |
|----------|---------|
| `backup_target <suffix> <extension>` | name this run's backup, set `BACKUP_TARGET_PATH`, create its directory |
| `backup_epoch <name>` | timestamp to epoch |
| `backup_listed [dir]` | the timestamp directories, oldest first |
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

### It is sourceable, and that is how the secondary stage avoids knowing anything

The generated script ends its definitions with:

```bash
[ "${BASH_SOURCE[0]}" = "${0}" ] || return 0
```

Executed, it takes a backup. **Sourced, it defines the module's vocabulary and returns**, so the
secondary stage can source a module's own `backup.sh` and get `BACKUP_FULL_SUFFIX`,
`BACKUP_DELTA_SUFFIX`, `backup_is_full`, `backup_listed`, `backup_pruned` and the rest — for *that*
module — without supervisor containing a single module-specific line. The secondary stage decides the
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
- write to a temporary name and rename on success, so the secondary stage never copies a half-written
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

### Retention, primary stage

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
   `${SERVICE_INSTALL}/backup.sh` — which `probe_lib_install.go` already records as
   `installService.backupEnabled`. Do not add an `install_pre.sh` or `install_prep.sh`; per-module
   release hooks are retired and `install.sh`'s own `run_backup` covers the release-time call for
   every module at once.
6. **Do not add it to `src/resources.txt`.** The script reads its environment at runtime and holds
   no `${VAR}` placeholders.
7. **Check the result**: a successful run leaves exactly one backup named
   `<service>_<timestamp>_<version>_full.<extension>`; a failed one leaves no file and no directory. Running
   it twice inside `BACKUP_SKIP_HOURS` **from the same version** must skip, and running it again after
   the version has moved must not. Sourcing it must produce no backup.

## Driver — planned

**`supervisor` runs the schedule, in Go, from its own container.** There are exactly two invokers of
a module's `backup.sh` and they answer different questions:

| Invoker | When | Why |
|---|---|---|
| `install.sh`'s `run_backup` | at release, before the old home is replaced | a safety copy of the version being upgraded away from — built |
| `supervisor`'s backup probe | daily, at `backupScheduledHour` | the estate's actual backup cadence — planned |

Per-module release hooks are gone: `run_backup` sits in the **root** `install.sh`, selects on
`${SERVICE_INSTALL}/backup.sh` existing, runs only for `COMMAND=install` with
`BACKUP_SKIP_HOURS=24 BACKUP_SERVICE_RESTART=false` under `timeout 1800`, and aborts the install if
the backup fails. That is one call site for every module and needs nothing from this plan.

**Supervisor has no `backup.sh` of its own.** The whole driver is
`internal/probe/probe_impl_backup.go` and the broker facility beside it, `internal/probe/probe_lib_broker.go` — no
`write_container_backup()`
call in `supervisor/generate.py`, no `src/build/resources/backup.sh` snippet, no supervisor entry in
the enrolled-module set. It does ship **one** script of its own, `mount.sh`, and the distinction is
worth stating precisely: `mount.sh` is not a backup, does not participate in the primary stage and is
not produced by the backup generator — it makes the estate's disks *available*, which is a
host-and-fstab job that shell does natively and Go would only wrap. Nothing about producing,
naming, promoting or thinning a backup is expressed in shell by supervisor. The
previous design put the driver in supervisor's own generated script and let Go schedule it; that
inverted the responsibilities, because everything the driver does — discovering modules, ordering
stages, timing them, writing a machine-readable result, judging staleness, feeding three metrics —
is already what the Go process does for every other subject on the host, and none of it is
module-specific shell.

**The driver is a probe, because a probe is the only thing this module has that produces a metric.**
`verifyProbes()` panics unless every metric ID has exactly one registered probe, and `registerProbes`
panics if two claim the same one, so a driver living outside that set could not own a reading. So
`backupProbe` is registered like `hostProbe` and `servicesProbe`, and it takes
`host/failed_backups` and `host/used_backup_space` out of `hostProbe`'s `metrics()` and into its
own. **`service/backup_status` does not move**: it is produced inside `servicesProbe`'s loop over
services, where the service is registered and its `ServiceIndex` known, so `servicesProbe` reads
that module's `success_bool` from the snapshot `backupProbe` publishes — the same division
`installReader` already has with the two probes that read it.

**Its `run` and its `daily` are two different jobs on two different goroutines, and that separation
is the point.** `run(ctx, isPulse)` is ordinary probe work — it parses the newest `status.json` on
the `--cache-period` refresh and stores the three readings, taking milliseconds and never blocking.
the run `scheduled(ctx, hour, crossed)` starts takes hours. Putting the second on the poll goroutine is the
mistake `engine_database.go` already made once: `probe.Run` executes every probe *and* `onPulse`
inline on the ticker goroutine, so a blocking call there stops the host sampling entirely, and
`RunAllProbesOnce` would additionally cancel it after three pulses.

### The schedule

**There is no backup schedule flag, and no backup scheduler.** There is one generic loop that says
what hour it is, and each plugin decides whether that hour is its own:

```go
type scheduledProbe interface {
    probe
    scheduled(ctx context.Context, hour int, crossed bool)
}
```

- **`probe.RunScheduled` ticks every minute** and calls `scheduled(ctx, hour, crossed)` on every
  probe implementing the interface. `hour` is the local hour 0–23; `crossed` is true only on the
  first tick of a new hour.
- **The two cadences are one interface.** A task that must run continuously ignores `crossed` — the
  backup reaper does, because it bounds how long a dead run leaves the disk powered and an hourly
  reap would leave it on for up to an hour. A task that must run once a day gates on
  `crossed && hour == <its own const>`. So the reaper is an ordinary method of `backupProbe` rather
  than a second published concept, and a future plugin picks its cadence by which argument it reads.
- **The hour is the plugin's const, not a flag.** `backupScheduledHour = 1` sits in
  `probe_impl_backup.go`'s const block beside the other backup constants. There is no `--daily-time`, no
  `config.DefaultDailyTime`, no `Periods.DailyMinutes` and no HH:MM parsing — retiming the estate's
  backup is a code change and a release, the same policy an in-place `.env` edit already carries.
  A flag was built first and removed: it made the estate's cadence an operator input that no
  operator had ever changed, and put the one number that decides when the backup runs somewhere
  other than beside the backup.
- **The loop owns the edge detection, so no plugin repeats it.** `scheduleSeed(now)` returns the
  hour the process started in and that hour counts as already crossed; `scheduleFires(now, fired)`
  is `now.Hour() != fired`. Both are pure and table-tested.
- **No catch-up, and now it is true.** The rule was always "a host down at 01:00 has missed that
  day", but the day-granular gate that first implemented it did fire late — a host asleep from 00:30
  to 05:00 woke and ran the backup at 05:00. Hourly firing drops that: the woken hour is the hour
  offered, and the backup ignores it. A backup storm on every restart is worse than a late run, and
  the staleness rule already reports the gap.
- **The crossing is a wall-clock question, so it uses `config.NowIncludingSuspend()`.** A monotonic
  reading would miss it entirely across a suspend — the split the *Clocks* section of `CLAUDE.md`
  records.
- **It runs for `serve` only.** `engine.RunAllProbesPublishLoop` starts `go probe.RunScheduled(ctx)`
  and the watch loops do not, so a `watch` on the dev machine cannot fire the estate's backups and
  `RunAllProbesOnce`'s three-pulse deadline cannot cancel a run mid-flight. It must sit below
  `probe.Create`, which is what sets the `execProbes`/`execConfigPath` package vars it reads.
- **Only a crossing logs, at DEBUG.** Twenty-three of every twenty-four are no-ops for the one probe
  that implements the interface, and a no-op must never log at INFO. The INFO timeline stays one
  line per actual run, logged by the backup probe itself.

**Anything else wanting a cadence hangs off the same loop**, as one more implementer of
`scheduled`, rather than a second scheduler.


### What the probe does when the gate fires

**The probe schedules; the stage scripts do the work.** It discovers who takes part, allocates the
run's `run_id`, starts each stage in order, times it out, and rolls the results up. It performs no
copy, mounts nothing and knows no module's format — those live in *Stage scripts and the broker
namespace*, and the division is what lets a stage be run by hand with supervisor stopped.

Inputs come from `config.json`, already loaded, already carrying everything needed — there is no
second config file and no `/etc/fstab` discovery:

- `.asystem.host` → this host and, via `.asystem.schema[]`, its share `index`
- `.asystem.schema[] | select(.host == $host) | .services[]` → the modules configured for this host

Participation is `installService.backupEnabled` from `probe_lib_install.go`, which already `Lstat`s
`<install>/<service>/latest/backup.sh` on every snapshot — so the probe reuses the install snapshot
rather than walking the tree itself, and a module enrolling or leaving is picked up by the existing
stat fingerprint with nothing new to invalidate.

A host's stages run **serially, in order**, because each depends on the one before: the secondary
stage has nothing to copy until the primary stage has produced it, and the tertiary stage nothing to
mirror until the secondary stage has been written and thinned. An `edge` host runs the first two; a
`server` runs all three.

So, per run:

1. allocate the `run_id`, create the run directory, publish `supervisor/<host>/backup/status`
2. for each stage this host runs, in order, exec `/asystem/etc/backup.sh <stage> start` with the
   `run_id`, and wait
3. on a stage exceeding its deadline, exec that stage's `stop.sh`, record the stage failed and
   **stop** — a stage whose predecessor did not finish has nothing sound to work from
4. read the stage and module documents the scripts wrote, roll them into `<run>/status.json`, and
   republish
5. on the leader alone (a `server`), once every expected `server` has reported a terminal state or
   the lease has expired, switch the outlet off

**It also watches for runs it did not start.** A stage invoked by hand publishes the same topics, so
the probe adopts it: an in-flight stage with an `expires_ts` in the future is a run in progress
whoever launched it, and one whose `expires_ts` has passed is timed out and gets its `stop.sh` and
the outlet turned off like any other. That is the whole reason liveness is published rather than
inferred — see *Payload specifications*.

### Powering and mounting the backup disks

**The `/backup` disks are on a switched outlet and are unmounted between runs.** `rack_backup_plug`
— a Sonoff BasicR2 in the rack, already declared in
`src/meg/tasmota/src/build/resources/devices/` and already a Home Assistant switch entity — powers
**every `server` host's USB `/backup` drive** at once. The `/share` disks are **not** on it: they
carry live data and stay mounted, so the secondary stage writes into `/share` with no power step.
Only the tertiary stage needs the outlet, and it cannot simply `rsync` into `/backup` and hope —
nothing is mounted until the drive has been on long enough to spin up and enumerate.

**`mount.sh` owns the mounting half, and it is generated like everything else supervisor ships.**
Its source fragment is `src/build/resources/mount.sh` and `fab generate` writes
`src/main/resources/image/mount.sh` with the standard banner — the same path the three health checks,
`broker.sh` and the stage scripts take. **Hand-authoring it was the earlier decision and it is
reversed**: the argument was that generation exists to remove repetition between modules and only
one module has this problem, which held while `mount.sh` was the single exception, and stopped
holding the moment the six stage scripts arrived generated. Two conventions for shipped scripts in
one module is a worse cost than a `write_container_mount()` that no other module calls, and the
banner is what stops somebody editing the copy under `image/` and losing it on the next generate.
(The generator was first written into the shared `container.py`; it now lives in this module's own
`generate.py` — see the deviation below. The argument above is unaffected: it was always about
generating rather than hand-authoring, never about where the generator sits.)
It takes a phase, in the shape `broker.sh [sweep|publish]` already established:

```
/asystem/etc/mount.sh up      # wait for readiness, mount what fstab declares, assert
/asystem/etc/mount.sh down    # unmount what it mounted, leaving the outlet alone
```

**The switch is not in the script.** `mount.sh` never touches the broker, and its whole subject is
fstab and mountpoints. The publish is its caller's — `backup/secondary.sh` and `backup/tertiary.sh`
publish `ON` and read the plug's retained state back before calling `mount.sh up`, which is what
lets a manual stage run with no supervisor and no leader in the picture. `probe_impl_backup.go` keeps the
same held session for the election and the switch-off. **Never publish
to the device's `stat` topic** — that is the device's to write, and faking it is the same error as
publishing `homeassistant/status` on Home Assistant's behalf. A plug already on answers immediately
and costs one round trip.

**The plug's topic comes from `config.json`, so no estate literal reaches the Go.** `generate.py`
writes a `backup` block beside `schema` — naming the plug's command and state topics — **for
`server` form-factor hosts only**, the same hosts that own a `/backup` disk. The probe reads it
through `config` as it reads everything else, and the boundary test below is unchanged — the driver
still contains no `rack_backup_plug`. A host with no `backup` block never switches anything, never
mounts `/backup` and runs no tertiary stage: `edge` hosts get no block, and `client`/`network`/`ignore`
hosts get no schema entry at all. The block's presence *is* the "runs the tertiary stage" flag —
one source of truth, derived from `.hosts`.

**`up` does three things, in order, and each is idempotent:**

1. **Wait for readiness.** A spinning disk is not ready when the relay closes. The script waits for
   the devices behind the fstab entries to appear, bounded by `mountReadySeconds`, polling rather
   than sleeping a fixed period — so a run finding the disks already spun up costs milliseconds and
   one finding them powered down still waits as long as it has to.
2. **Mount what fstab declares, and only that.** The script never invents a mount: it reads
   `/etc/fstab`, selects the entries it is responsible for, and `mount`s each by mountpoint. **The
   fstab entry is the declaration and the script is the enactment**, which is the same division
   `storage/install_prep.sh` already uses when it reads `/etc/fstab` for `/share` `ext4` lines to
   decide which shares to publish over samba.
3. **Assert.** Every mountpoint it was responsible for is `mountpoint`-clean, or `up` fails with the
   list of those that are not.

**It reads the fstab line, never the host name.** On a `server` the `/backup` entry is a local
filesystem type — a directly attached disk behind the switched outlet — and `mount.sh` waits for it
to spin up, mounts it and asserts it. There is no `cifs` `/backup` anywhere: an `edge` host has no
`/backup` at all. So the script needs no local-versus-remote branch and no per-host branch:

| Host (form-factor) | `/share/<n>` | `/backup` |
|---|---|---|
| `mad`, `max`, `may`, `meg` (`server`) | local, its own numbered shares, always mounted | local, its own USB backup disk, `noauto`, mounted by `mount.sh` around the tertiary stage |
| `jen`, `jil` (`edge`) | `cifs` from a `server`, mounted automatically at `/share/<n>` | none — the `edge` host never mounts `/backup` |

**`mount.sh` runs on `server` hosts only, and its whole subject is `/backup`.** A `server`'s
`/share/*` mounts are `auto` and permanent, so the script asserts them with `mountpoint` and does
nothing else; `/backup` is the `noauto` entry it powers up, waits for, mounts before the tertiary
stage and unmounts after. An `edge` host ships `mount.sh` too — every module ships every generated
script — but its `config.json` carries no `backup` block, so it never invokes it and never switches
the plug.

**Switching on and switching off are not the same problem.**
One plug powers every `server`'s `/backup` drive, so switching **on** is idempotent and safe from
anywhere, while switching **off** would cut another `server` mid-`rsync`. So switching on is harmless
wherever it happens and **the tertiary stage script does it for itself**, `mount.sh down` unmounts
and leaves the outlet alone, and the outlet is switched **off** by exactly one `server` per day,
elected. `edge` hosts are not candidates — they never touched the plug. See *The cluster singleton*.

`rack_backup_plug` publishes no energy entity today, so nothing reports what an outlet left on
costs. Adding one — the shape `rack_outlet_plug` and `ceiling_network_switch_plug` already use — is
what would turn "wasteful" from a judgement into a number.

**A Tasmota warm restart leaves the relay alone**, so `tasmota`'s `broker.sh` recovery fragment
restarting its devices cannot power the disks down mid-run — but note `rack_backup_plug` is an
ESP8285, where that guarantee holds; the ESP32 caveat in the root `CLAUDE.md` does not apply here.
Its `PowerOnState` should nonetheless be confirmed, since a cold power-up of the plug itself decides
whether the disks come back after a rack outage.

**Failure is a recorded stage failure, never a partial copy.** If the plug does not answer, the
`/backup` disk does not appear, or its mount does not assert, the tertiary stage is marked
`success_bool: false` with the reason in `logs/tertiary.log`. The secondary stage does not depend on
any of that — it writes to an always-mounted `/share` — so a dead backup disk costs the tertiary
stage alone. The primary and secondary results stand on their own: the day's backups exist locally
and on the share, and are promoted on the next successful tertiary run, because the copy from the
secondary stage is additive and no data is lost by a skipped promotion.

### The cluster singleton

**One `server` per day switches the outlet off. That is the whole of it.** Every `server` powers the
outlet *on* for itself and runs its own tertiary stage without waiting for anybody — see *Stage
scripts and the broker namespace* — so the singleton exists for the one decision that cannot be
taken locally, because cutting power would take out another `server` mid-`rsync`. `edge` hosts are
outside the election entirely: they never mount `/backup`, never run a tertiary stage, and never
touch the plug. The election runs on the broker every host is already connected to, using only
retained messages and a last will — no new dependency, no new service, and nothing a vernemq
release carries over, since that release flushes the retained store, which is correct because a
release should void a lease rather than preserve it. A plain broker *restart* now preserves the
store, so a retained lease can outlive the session that held it — the will only fires while the
broker is up to publish it — and what bounds it there is the lease's own `ExpiresTS`, checked by
`expired()` at every read, not the volatility of the store.

**It is deliberately more than the job appears to need.** A fixed host named in `config.json` would
switch off too, until that host was down or decommissioned and the disks stayed powered with nothing
reporting it. The lease also does a second job the switch-off does not: it bounds a run at
`backupRunCeiling` and is what the staleness window is built from.

Four retained topics, all QoS 1, specified in full under *Stage scripts and the broker namespace*:

| Topic | Payload | Written by | Cleared by |
|---|---|---|---|
| `supervisor/cluster-all/backup/leader` | the lease — `host`, `epoch`, `timestamp`, `expires_ts` | a candidate claiming it | the leader when done, or its last will |
| `supervisor/cluster-all/backup/status` | the estate roll-up, including whether the plug is believed on | the leader | the leader when done |
| `supervisor/<host>/backup/status` | that host's run document, replacing the old bare `done/<host>` timestamp | each host's `serve` | its own next run |
| `supervisor/<host>/status` | `<online\|offline>` | **already exists** — each `serve` | its own last will |

**There is no `power` topic.** It existed so a follower could learn that the leader had mounted the
disks; `backup/tertiary.sh` now waits for its own USB devices to appear, which is a better test than
being told, and works identically for a manual run with no leader at all.

**These topics must be declared and must not be swept**, which is specified once in *Declaring this
in the schema* and not repeated here. The part that matters to the lease: `broker_topic_glob_data`
is `supervisor/${SUPERVISOR_HOST}/#` today and the `${VAR}` placeholder matches as a wildcard, so
`broker.sh sweep` at a supervisor release would **delete a lease a different host is holding,
mid-run**. Narrowing it to `.../data/#` is what puts the whole backup namespace outside the sweep.

**The client is supervisor's own, and it is not the engine's.** `probe_lib_broker.go` is a small
short-lived client — connect with a last will, publish retained, read one retained payload back,
close — used by the election and by the plug. It is not `engine`'s paho session: `probe` importing
`engine` inverts the dependency, and the lease needs a will of its own that the engine's session
cannot carry. Keeping it small is the point; it is not a second implementation of reconnect, backoff
and SUBACK reading, because a run that cannot reach the broker for a few seconds should fail its
election rather than retry for ten minutes.

**Election is publish, settle, confirm — and it is a mutex, not a consensus protocol.** The broker
serialises writes to one retained topic, so the last write wins and every reader converges on the
same value. That is all this needs:

1. Only `server` form-factor hosts are candidates — `mad`, `max`, `may`, `meg`, in that order — since
   only they own a `/backup` disk and a `config.json` `backup` block. An `edge` host has no block, so
   `probe_impl_backup.go` never enters the election on it.
2. A candidate publishes the election payload retained to `supervisor/cluster-all/backup/leader`, with its
   **last will set to an empty payload on that same topic**, so a crash clears the lease rather than
   stranding it.
3. It waits `brokerSettle` and reads the topic back. Its own value means it leads; anyone else's
   means it follows. Two hosts publishing at once both read the same final value, so exactly one
   leads and the other yields without a negotiation round.
4. A candidate finding a lease that is **already held and not expired** follows immediately and does
   not publish. One finding an **expired** lease claims it, which is what recovers a leader lost to
   a hard reset before its will was delivered.
5. If no lease can be established within `leaderTimeout`, the `server` **runs all its stages anyway**
   and records that no leader was elected. A failed election costs the outlet being switched off at
   the end, not a backup — the scripts need no leader to run, and the next day's leader finds an
   expired lease and clears it. This is weaker than it was and deliberately so: when the stages
   depended on `power=ready`, a failed election cost two of the three.

**The lease is the timeout, and it is `backupRunCeiling` — five hours.** That one constant on
`probe_impl_backup.go` does three jobs, which is why it is one constant and not three: it bounds the
leader's hold, it is the ceiling on a whole run, and it is the allowance in the staleness window
(`backupStaleWindow` = 24 h + `backupRunCeiling` = **29 hours**). A run that has not finished in
five hours is not going to, and holding the outlet on past that is worse than cutting it.

**The leader's init and destroy are the singleton, and nothing else is.** Everything between them is
ordinary per-host work happening in parallel:

- **init** — allocate the run timestamp and publish the lease. It no longer switches the plug on:
  `backup/tertiary.sh` does that for itself, so a manual tertiary run needs no leader.
- **destroy** — switch the plug off, then clear `election` and `status`. Reached when every expected
  `server`'s `supervisor/<host>/backup/status` reports a terminal state for this timestamp, or when
  the lease expires, whichever is first. **Switching off is still the leader's alone**, because
  another `server` may still be writing. `edge` hosts are not in the expected set — they never write
  to `/backup`, so the leader does not wait on them.
- **the expected set is read, not configured** — every `server` whose retained
  `supervisor/<host>/status` is `online` and which carries a `backup` block in `config.json`. `edge`
  hosts are excluded by having no block. So a `server` that is down does not hold the outlet on for
  five hours, and no list has to be maintained anywhere.

**The leader is an ordinary `server` in every other respect** — it runs the same three stages as
every other `server`, on its own gate, and its own terminal state counts like any other.

**The primary and secondary stages are outside all of this.** They write only to `/home/asystem` and
an always-mounted `/share`, need no powered disk and no election, so they run immediately at
`backupScheduledHour` on every `edge` and `server` host with no waiting and no dependency on the broker.
Only the tertiary stage is wrapped. That is worth being explicit about, because it means **a total
failure of the election still produces the day's backups on the share** — it only costs the mirror
to `/backup`.

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
clears `supervisor/cluster-all/backup/leader` if the broker notices, and the `expires_ts` lets the next day's
candidate claim it if the broker does not. The outlet stays on in the meantime, which is the safe
direction to fail.

### The run's output

**Supervisor's backup tree sits exactly where every other module's does — a sibling of the versioned
homes, not under `latest`.** The run's record *is* supervisor's backup, so it goes to
`/home/asystem/supervisor/backup/`, the same `<data root>/backup` shape as
`/home/asystem/postgres/backup/`, named and timestamped identically, and the secondary and tertiary
stages promote it as they find it with no special case. Two reasons it is **not**
`/home/asystem/supervisor/latest/backup/` (nor the container-relative `/asystem/mnt/backup/` that
resolves to it): `install.sh` copies the old home into the new one on every deploy, so a `backup/`
inside `latest` would be dragged forward — the whole accumulated history — on every supervisor
release, exactly the trap *item 2* documents for influxdb3; and a sibling path is the module
contract, so the secondary stage's `rsync` of supervisor's root stops being an exception. It needs
the `/home/asystem` same-path bind from build-order step 4, and then the path is identical in the
container and on the host:

| Tree | Container and host (same path) | Holds | Written by |
|---|---|---|---|
| **backup** | `/home/asystem/supervisor/backup/` | one directory per run — `status.json` and `logs/` | the driver, every run |

An earlier design had two — a `state/` tree the driver wrote and a `backup/` tree holding a
`supervisor_<timestamp>_<version>_full.tar.gz` of it, produced at the head of the primary stage. The tar
is gone: it was a second copy of a directory already sitting where backups go, it could never
include the run that produced it, and it cost supervisor a primary-stage step no other module has.

**A run directory carries no `_full` / `_delta` suffix, and does not need one.** Nothing here is
incremental — every run's record stands alone — so the classification the secondary stage uses to keep a
sparse point self-contained is trivially satisfied by every directory in this tree.

The run directory layout is fixed and is the contract every reader depends on:

```
/home/asystem/supervisor/backup/
├── .lock                                    flock, one run per host
└── <timestamp>/
    ├── status.json                          → backup/status
    └── stage/
        ├── primary/
        │   ├── status.json                  → backup/stage/primary/status
        │   ├── output.log                   the primary stage's stdout and stderr
        │   └── service/
        │       ├── postgres/
        │       │   ├── status.json          → backup/stage/primary/service/postgres/status
        │       │   └── output.log           that service's backup.sh stdout and stderr
        │       └── influxdb3/
        │           ├── status.json
        │           └── output.log
        ├── secondary/
        │   ├── status.json                  → backup/stage/secondary/status
        │   └── output.log
        └── tertiary/
            ├── status.json                  → backup/stage/tertiary/status
            └── output.log
```

`<timestamp>` is `%Y-%m-%d_%H-%M-%S` local — the same format the service backups use, so a run
directory and the backup directories it produced sort together and read the same way.

**The tree is the topic namespace, and that is the whole rule**: `<run>/<path>.json` is
`supervisor/<host>/backup/<path>`, so a path and a topic are one extension strip apart in either
direction and `find <run> -name '*.json'` enumerates exactly what the run published. It replaced a
flat tree in which a stage result and a service result were siblings, which forced two hardcoded
lists — a `backupReservedDir` in Go and a matching `case` in `backup/secondary.sh` — to know that
`primary`, `secondary`, `tertiary` and `logs` were not service names. Under an explicit `service/`
level no name can be mistaken for a stage, and both lists are gone.

**Each node carries its own log beside its document.** `output.log` is named for what it is rather
than for the node, since restating the directory is only what the old `logs/primary.log` had to do
to survive in a separate tree; there is no `logs/` subtree any more, so "how did this one thing go"
is one directory rather than two that must be kept in step.

**The tree sits inside the versioned home, which is deliberate and has one consequence.** Every
other service's backup root is `/home/asystem/<service>/backup`, a sibling of the versioned homes, so
that `install.sh`'s `cp -rfpa` of the old home into the new one does not duplicate it. Supervisor's
is inside `latest/` instead, so **a release copies the run history forward** — which is what keeps it
across a deploy, and is bounded by `retire_home` pruning the older homes and by the thinning below.
Watch the cost: supervisor releases often, and the tree grows by one directory a day per host.

**Supervisor thins its own tree, on the same tiers as everything else and by date alone.** It has no
`backup.sh`, so the secondary stage has nothing to source and no `--prune` to delegate to, and it has no
suffix to classify by — so the probe applies `BACKUP_RETAIN_DAYS` at the primary stage and the same
grandfather-father-son tiers at the secondary stage, reading the timestamp from the directory name. The
alternative — dense locally and append-only on the share — was rejected for the vocabulary rather
than the bytes, which are negligible either way: one retention policy applies to everything the secondary
stage holds, and the component *doing* the thinning is the worst possible place to introduce an
exception to it. It also keeps the record at the same depth as the backups it describes, so a monthly
point holds a backup and the account of the run that produced it.

**The tree mirrors the broker namespace exactly, and that is the point.** A file's path under the
run directory is its topic under `supervisor/<host>/backup/`, with `/status.json` reading as
`/status` — so `<run>/postgres/status.json` is `supervisor/<host>/backup/postgres/status` and there
is one mechanical rule, no translation table, and nothing to keep in step by hand. **The documents
and the payloads are byte-identical**: the shapes are specified once, in *Payload specifications*,
and are not restated here.

**One nested document was the earlier design and it was wrong twice over.** It expressed the
hierarchy a second time, in braces, when the topic tree already expresses it — the same duplication
that got `src/build/resources/backup/` deleted. And it gave three stage scripts one file to write,
which is a read-modify-write race with no lock in sight; decomposed, **each file has exactly one
writer**, the same rule the topics follow. Nothing is lost: every field of the nested form appears
in one of the three documents, and `stage.primary.module.postgres` is now simply
`<run>/postgres/status.json`.

**Each document is written once, at the end of the thing it describes, and never updated in place.**
A partially written document is indistinguishable from a completed run that failed, which is
precisely the ambiguity the staleness rule below has to resolve, so each is written to
`status.json.tmp` and renamed. **In-flight state lives on the broker and nowhere else** — that is
what `state` and `expires_ts` are for, and it is why a run with the broker down is invisible until
it finishes rather than half-recorded on disk. The logs are the live view; the documents are the
record.

The three shapes share one set of keys, so a reader learns them once and applies them everywhere:

| Key | Meaning at every level |
|---|---|
| `started_ts` / `finished_ts` | an **RFC 3339 instant**, local with offset, so a moment is comparable without knowing the host's zone — distinct from the portable timestamp, which names a run rather than measuring one |
| `duration_s` | wall seconds, `finished_ts - started_ts` |
| `success_bool` | this level completed without a failure; a stage is true only when every module under it is true |
| `disk_usage_perc` | percentage used of the filesystem this level **wrote to** — the module data volume, `/share`, `/backup`. At the run level it is **`/backup` alone**, not a roll-up, because that is the volume `Used BKP` names — absent from an `edge` host's run document, which has no tertiary stage |
| `file_count` | files this level wrote or holds at its destination |
| `size_mb` | megabytes this level wrote or holds at its destination |

**`primary`, `secondary` and `tertiary` are the same three words everywhere** — the stage table, the
directory names, the log file names, the topic levels, the Go identifiers and the log subjects.
There is no second vocabulary and no translation anywhere in the run, which is what lets one path
rule carry a document to its topic.

**This directory format is the specification, and `src/build/resources/backup/` is not.** The
skeleton committed there was a sketch of this section written as files; with the format stated here
it is redundant, so **delete `src/all/supervisor/src/build/resources/backup/` entirely**. Nothing
generates it, nothing reads it, and a second copy of a format that only Go writes could only drift.

**The filesystem is still the truth about a backup; `status.json` is the truth about a run.** A
module backup exists at its final name only if it succeeded, and its timestamp says when — that has
not changed and no status document overrides it. What `status.json` adds is the things the
filesystem cannot say: which stage failed, how long each took, how full each destination is, and
which modules were even attempted.

### Stage scripts and the broker namespace — planned

**Each stage is a self-contained bash pair, and supervisor schedules rather than implements it.** The
driver decides *when* a stage runs, times it out and rolls up the result; the stage itself is a
script the driver execs from inside its container and which can equally be run by hand from a host
shell — the same-path binds make the two identical. That division is what makes a backup recoverable
when the thing that schedules it is the thing that is broken.

```
<install>/supervisor/latest/image/backup.sh                              the runner, reachable from a host shell
<install>/supervisor/latest/image/backup/lib.sh                          the functions it sources
<install>/supervisor/latest/image/backup/{primary,secondary,tertiary}.sh the stages
/asystem/etc/backup.sh <stage> [start|stop] [run-id]                     the same files, in the container
/home/asystem/supervisor/backup/<timestamp>/                             written, one per run, same path both sides
```

**The scripts are shipped artefacts and belong in `image/`, beside `mount.sh` and `broker.sh`.**
That is where every generated script this module ships already lives — the host's
`<install>/supervisor/latest/image/` holds `broker.sh`, `broker/`, `config.json` and the three
health checks today — and it is reached inside the container at `/asystem/etc/` by the mount that
already exists. So the stage scripts need **no new mount and no new convention**: they are
hand-authored in `src/main/resources/image/`, and ship like everything else. *(They were generated
from `src/build/resources/backup/<stage>/{start,stop}.sh` until the generators were removed — see
* Removing the stage generators* at the end.)*

**That is also what settles `backup` against `backups`.** The plural was proposed to keep supervisor's
run directory from colliding with the module-level `backup/`, and there is no collision:
`/home/asystem/postgres/backup/` and `/home/asystem/supervisor/backup/` are distinct by the module
segment, and supervisor's tree is now a sibling of `latest/` like every other module's rather than
nested inside it. Splitting on the plural would put `backup/` and `backups/` side by side in one
parent, distinguished by a single letter, which is the kind of naming that
eventually costs somebody an afternoon. Splitting on **what the estate already splits on** costs
nothing: `image/` is what we ship and `/home/asystem/…` is what we write, so both can be called
`backup` and neither is ambiguous. The word stays singular everywhere, and a `backups/` plural
is not needed.

**Logs stay in the run directory and are not duplicated beside the scripts.** A stage writes
`<run>/logs/<stage>.log` as specified in *The run's output* — one layout, reachable at the same path
from the host and the container, and it keeps a run's log beside the `status.json` that describes
it. A `<timestamp>.log` per stage sitting next to the scripts would be a second copy of the same
information in the shipped tree, which a release would then carry forward as though it were an
artefact.

**`start.sh` runs the stage; `stop.sh` tears it down.** Both are per stage, both are idempotent, and
neither knows about the other stages. For the tertiary stage `start.sh` calls its own `stop.sh` on
the way out, so `/backup` is mounted only for the span of the copy:

**primary** — for each module configured on this host, **serially**, skipping any with no
`backup.sh` and any whose container is not running:

1. execute `${SERVICE_INSTALL}/backup.sh` with the policy variables and nothing else — it sources
   its own `.env` for everything about itself, so only `BACKUP_SKIP_HOURS` and
   `BACKUP_SERVICE_RESTART` are passed, exactly as `install.sh`'s `run_backup` passes them
2. exit `0` is produced or throttled by its own `BACKUP_SKIP_HOURS`, non-zero is failed; the rest of
   its output is that module's log
3. it writes `/home/asystem/<service>/backup/<timestamp>/<service>_<timestamp>_<version>_{full,delta}.<ext>`
4. write `<run>/<service>/status.json` and publish the matching topic
5. never read a data directory, choose an exclusion or parse a backup — the module owns its format,
   its throttle and its pruning

**Supervisor does not back itself up, because its run record already is its backup.** There is no
supervisor `tar` and no supervisor step at the head of the stage: the run directory this run is
about to write sits in a backup root named and timestamped like every other module's, so the later
stages promote it as they find it. The one consequence is unchanged — this run's own record is
written after the stages it describes, so it reaches the secondary stage on the following day.

**secondary** — no preamble (the share is always mounted), then for each module whose primary stage
succeeded, so a bad backup is never promoted:

1. `rsync -a --link-dest` of the previous copy, no `--delete`, of `/home/asystem/<service>/backup/`
   into `/share/<index>0/backup/<service>/` — `<index>0` from `config.json` on a `server`, the
   lowest-numbered mounted `/share/<n>` from fstab on an `edge` host — with `--temp-dir` (see
   *Surviving a hard reset*).
   Supervisor's own root is `/home/asystem/supervisor/backup/`, the same `<data root>/backup` shape
   as every module, so it is not a special case: the script copies the directory supervisor writes
   itself exactly as it copies a module's
2. source that module's `backup.sh` in a subshell, so `backup_is_full`, `backup_is_delta` and
   `backup_listed` are its own, or call `backup.sh --prune <dir>` as a subprocess
3. thin to the GFS ladder — the tiers, the per-module depths and the `_full` / `_delta` rule are
   specified once in *Retention, secondary stage* and are not restated here

**tertiary** — `server` hosts only, the preamble first, then once for each mounted share on this host
rather than only the principal one, both sides guarded on `mountpoint`:

1. the preamble — publish `ON`, then `mount.sh up` for `/backup`
2. `rsync -a --delete --exclude tmp/` of `/share/<n>/` into `/backup/share/<n>/` for each mounted
   share, `tmp` being scratch never worth replicating, with `--temp-dir` for the same reason as the
   secondary stage
3. snapshot and thin, per *Filesystem, tertiary stage*
4. `backup.sh tertiary stop` — `mount.sh down` to unmount `/backup`, then exit `0`. It runs here on success
   exactly as it runs on a kill or a timeout, so `/backup` is never left mounted between runs

**Guard on `mountpoint` before every write**, even though the preamble has already asserted it — the
mount can lapse in between, and writing to an unmounted `/share/10` silently creates the path on the
root filesystem and fills the OS disk rather than merely failing.

**`stop.sh` is the same three shapes, and for the tertiary stage it always runs.** Primary signals
the running `backup.sh` and lets it clean up its own temporary file; secondary kills the `rsync`.
**The tertiary `stop.sh` is the normal teardown, not only the abort path** — `backup/tertiary.sh`
invokes it as its last act once every share has replicated, and it also runs on a kill or a
timeout. It kills any `rsync` still going, runs `mount.sh down` to unmount `/backup`, and exits
cleanly. So a successful tertiary run leaves `/backup` unmounted exactly as a failed one does, and
the disk is idle before the leader cuts power. **None of the three switches the plug off**, ever —
that stays the leader's, on completion of the whole estate or on lease expiry.

**The preamble belongs to the tertiary stage alone, because it is the only stage that needs a
powered disk.** `/share` is always mounted, so the secondary stage writes straight into it; `/backup`
is the cold drive on the switched outlet. The preamble is two steps: publish `ON` to the plug, then
`mount.sh up`. **The waiting and the asserting are `mount.sh`'s, not the preamble's** — it already
polls for the fstab devices under `mountReadySeconds` and fails with the list of mountpoints that did
not come up, so a preamble that also waited would be a second implementation of the same loop. Both
steps are idempotent and reentrant, so a `server` finding another `server` has already powered the
outlet costs one round trip.

**Only the tertiary stage touches the plug, and only in one direction.** Switching on is idempotent
and safe from anywhere, so `backup/tertiary.sh` does it and the retained `power` topic is gone — a
script that can wait for its own devices to appear does not need to be told that somebody else has
powered them. Switching **off** is the estate-wide decision and stays with the leader, because
another `server` may still be writing: a `stop.sh` that cut power would take out every other tertiary
run in flight. So `stop.sh` unmounts and returns, and the outlet is switched off by the leader on
completion or on lease expiry, exactly as before.

**Run by hand, a stage detaches and still leaves a log.** Invoked manually a `start.sh`
re-executes itself in the background, `disown`ed, so the shell can log out and the run continues,
with output `tee`d to both its `<run>/logs/<stage>.log` and stdout. A run invoked by supervisor is the same
script with the same output; nothing branches on who called it except where the timestamp comes from.

**The timestamp is allocated at the level that starts the work, and it flows downward only.** A
supervisor-scheduled run allocates one timestamp and passes it to every stage it runs, which pass it
to each module's `backup.sh` and to the btrfs snapshot label, so one string traces a night's work
through every log, every payload and every snapshot. A stage or a module script run **by hand**
allocates its own timestamp, which does not propagate upward — the module backup directory is then
timestamped differently from any run that later promotes it, and that is fine and already true: the run
timestamp identifies the *run*, the backup timestamp identifies the *backup*, and both appear in the
payloads so neither has to be inferred from the other.

**Logs are trimmed by the scripts, on their own stage's policy** — and because a log lives in the
run directory, trimming a log means retaining a run directory. Primary keeps `BACKUP_RETAIN_DAYS`;
secondary and tertiary keep the GFS ladder. A log has no `_full` / `_delta`
distinction, so GFS degenerates to *newest per day, ISO week and month* — which is the intended
reading and costs nothing to implement. Each stage appends per module as it spools, so a log is
readable while the stage is still running rather than only at the end.

#### The broker namespace

**`status.json` is the record and MQTT is how it travels.** Every payload below is a projection of
the document already specified in *The run's output*, retained, QoS 1, published by whoever owns the
work it describes. Nothing new is invented for the wire.

**A script publishes directly, with `mosquitto_pub` and the module's own `.env`.** Both are already
on every host — `/usr/bin/mosquitto_pub`, and `BROKER_HOST` / `BROKER_PORT` / `BROKER_TOKEN` in
`<install>/supervisor/latest/.env` — so the connect block is three lines and depends on no container:

```sh
set -a; . "${INSTALL_ROOT}/supervisor/latest/.env"; set +a
mosquitto_pub -h "${BROKER_HOST}" -p "${BROKER_PORT}" \
  ${BROKER_TOKEN:+-u supervisor -P "${BROKER_TOKEN}"} -q 1 -r -t "${topic}" -m "${payload}"
```

The `${BROKER_TOKEN:+…}` form is the one `checkexecuting.sh` already uses, left unquoted so bash
splits it, and it never prints the token.

| Topic | Written by | Carries |
|---|---|---|
| `supervisor/cluster-all/backup/leader` | the candidate holding the lease | the lease |
| `supervisor/cluster-all/backup/status` | the leader | the estate roll-up |
| `supervisor/<host>/backup/status` | that host's `serve` | the host's run document |
| `supervisor/<host>/backup/<stage>/status` | that stage's `start.sh` | one stage's result |
| `supervisor/<host>/backup/stage/primary/service/<service>/status` | `backup/primary.sh` | one module's backup |

**One topic, one writer** — which is why the stage topics exist rather than three scripts writing
one host document. `primary`, `secondary` and `tertiary` are reserved words in this namespace and no
module may take one as a name.

**`supervisor/leader/` is a namespace, not a host**, and it is safe only while no host is called
`leader`. It sits outside `supervisor/<host>/` deliberately: a lease is estate state, and a topic
under one host's prefix would be swept by that host's own release.

#### Payload specifications

**Three field conventions, and the names carry the difference.** A `_id` is an identifier compared
for equality — its value is a portable timestamp, but nothing may parse it. A `_ts` is an RFC 3339
instant, measured and comparable. Everything else is a plain value. The suffix is what tells a
reader which operations are legitimate, which matters most where the two kinds sit adjacent in the
same object.

**`timestamp` is deliberately not reused as a field name here**, because supervisor already spends
it: `metric.Payloads()` declares `{Key: "timestamp", Kind: schema.KindInt}` — an epoch integer — on
the state payload every metric topic carries. Reusing the word for a `%Y-%m-%d_%H-%M-%S` string
would put one key name with two types in one module's declared payloads, and nothing would catch it:
`verify.sh` checks that topics are declared, never that a payload matches its shape.

`supervisor/cluster-all/backup/leader`

```json
{
  "host": "<text>",
  "epoch": "<number>",
  "run_id": "<portable timestamp>",
  "claimed_ts": "<rfc3339 instant>",
  "expires_ts": "<rfc3339 instant>"
}
```

`supervisor/cluster-all/backup/status`

```json
{
  "run_id": "<portable timestamp>",
  "state": "<idle|running|complete|failed|timeout>",
  "started_ts": "<rfc3339 instant>",
  "finished_ts": "<rfc3339 instant>",
  "duration_s": "<number>",
  "success_bool": "<true|false>",
  "power_bool": "<true|false>",
  "hosts_expected": "<number>",
  "hosts_reported": "<number>",
  "hosts_failed": "<number>"
}
```

`supervisor/<host>/backup/status`

```json
{
  "run_id": "<portable timestamp>",
  "state": "<idle|running|complete|failed|timeout>",
  "trigger": "<scheduled|manual>",
  "started_ts": "<rfc3339 instant>",
  "finished_ts": "<rfc3339 instant>",
  "expires_ts": "<rfc3339 instant>",
  "duration_s": "<number>",
  "success_bool": "<true|false>",
  "disk_usage_perc": "<number>",
  "file_count": "<number>",
  "size_mb": "<number>",
  "stages_run": "<number>",
  "stages_failed": "<number>"
}
```

`stages_run` is 2 on an `edge` host and 3 on a `server`, so `Fail BKP` is `stages_failed ÷
stages_run` and never divides by a stage the host was never going to run.

`supervisor/<host>/backup/<stage>/status`

```json
{
  "run_id": "<portable timestamp>",
  "state": "<idle|running|complete|failed|timeout>",
  "trigger": "<scheduled|manual>",
  "started_ts": "<rfc3339 instant>",
  "finished_ts": "<rfc3339 instant>",
  "expires_ts": "<rfc3339 instant>",
  "duration_s": "<number>",
  "success_bool": "<true|false>",
  "disk_usage_perc": "<number>",
  "file_count": "<number>",
  "size_mb": "<number>"
}
```

`supervisor/<host>/backup/stage/primary/service/<service>/status`

```json
{
  "run_id": "<portable timestamp>",
  "backup_id": "<portable timestamp>",
  "state": "<idle|running|complete|skipped|failed|timeout>",
  "started_ts": "<rfc3339 instant>",
  "finished_ts": "<rfc3339 instant>",
  "duration_s": "<number>",
  "success_bool": "<true|false>",
  "kind": "<FULL|DELTA>",
  "form": "<full|delta>",
  "version": "<text>",
  "file_count": "<number>",
  "size_mb": "<number>"
}
```

Three conventions hold across all five, and each earns its place:

- **`run_id` is the run**, `backup_id` is the artefact, and both are named `_id` rather than
  `_timestamp` on purpose. Their value *is* a portable timestamp, but their contract is **equality
  and nothing else** — never parsed, never compared for ordering, never converted between zones — so
  the name says identifier and the format is an implementation detail of how one is minted. Every
  payload carries `run_id`, so a night's work joins across hosts, stages and modules by string
  comparison and nothing has to be inferred from a time range.
- **`run_id` is a correlation id, not a primary key.** Every host taking part in one scheduled run
  publishes the same value — that is the whole point — so it identifies the run, not the publisher.
  What identifies a row is `run_id` plus the topic it arrived on.
- **`expires_ts` is liveness, and it is what makes a timeout possible.** A script publishes it
  ahead of itself and refreshes it as it works; past that instant the run is dead whatever the state
  says. It exists because **`mosquitto_pub` cannot hold a last will** — it connects, publishes and
  disconnects — so a `SIGKILL`ed stage would otherwise leave `running` retained forever. The leader
  reaps on expiry, the same rule the lease already uses.
- **`state` and `success_bool` are not redundant.** `state` is where the run is, `success_bool` is
  what it produced; a stage can be `timeout` with some modules already succeeded, and `Fail BKP`
  needs the second while the display needs the first.

#### Declaring this in the schema

**All of it can be declared, and most of the machinery exists.** `metric.Topics()` already emits one
`schema.Topic` per retained topic with `$HOST` / `$SERVICE` placeholders that `generate.py` binds
through `broker_entities`, and `metric.Payloads()` already emits `schema.Payload` trees that the
vernemq emitter renders into a leaf. The five topics above are five more templates with two more
placeholders (`$STAGE`, `$MODULE`) and five more payloads. Roles are fixed at
`state` / `command` / `availability`, so all five are `state` and are told apart by `match`, the
`fnmatch` tie-break the emitter already applies when one role carries several shapes.

Two bindings `generate.py` must supply, both derivable rather than declared: `$STAGE` is the three
reserved words, and `$MODULE` is the enrolled set — the modules shipping a
`src/build/resources/backup.sh` snippet — bound per host from `load_bootstrap_modules()` the way
`$SERVICE` already is, so a host declares only the modules it actually runs.

**One library change is needed: `broker_topic_glob_data` must accept a list.** It is a single string
today, used for three things — validating that every declared topic falls inside it, generating the
`broker.sh sweep`, and building the operator scripts' subscription filters — and
`supervisor/cluster-all/backup/#` cannot be expressed alongside `supervisor/${SUPERVISOR_HOST}/#` in one
glob. **Widening to `supervisor/#` is not an option**: the sweep would delete every other host's
retained topics on any supervisor release. The change is contained — the validation already loops,
and `describe`/`query`/`verify` already take a `globs` list — so the work is to accept a list at the
call site and thread it through `publish_script`. See item **16**.

**The backup namespace is deliberately outside `data/`.** *The cluster singleton* already narrows
`broker_topic_glob_data` to `supervisor/${SUPERVISOR_HOST}/data/#` so the lease survives a release;
the same narrowing keeps every topic here out of the sweep. That is correct rather than convenient:
a backup result is not a metric reading, nothing republishes it on a schedule, and a release must
not silently blank the estate's backup history.

**A vernemq release still wipes all of it, and only supervisor can restore it.** The retained store
is flushed deliberately by `vernemq/install_pre.sh` on every release, so a release drops every
payload above; the scripts run nightly and will not republish for up to a day, which would blank `Fail BKP` and `Used BKP` estate-wide. So each host's
`serve` **re-asserts its own `supervisor/<host>/backup/**` topics from the local `status.json` on
connect**, which is the replay-on-reconnect rule the estate already applies to every other
publisher. Two writers therefore touch a stage topic — the script while it runs, supervisor when it
reconnects — and the rule that keeps them honest is that **supervisor only ever republishes what is
on disk**, never a newer timestamp or a state the document does not carry.

### Metric wiring

Three metrics read the newest `status.json` **on their own host** and nothing else. The probe
resolves the newest run directory by timestamp, reads the document, and publishes through the existing
record cache, so the display, the broker and the database all follow with no further wiring. Each
treats a document older than `backupStaleWindow` as no answer at all.


**`Used BKP` is a last-known reading, not a live one**, and that is the honest answer for a disk
that is unmounted between runs — the stage that mounted it is the only thing that can measure it.
Its age is the run's, so a host whose tertiary stage has not run inside the staleness window reads
not-ok rather than reporting yesterday's percentage as though it were now.

**A host does not read its own backup topics back, and the difference is worth stating** — the
payloads in *Stage scripts and the broker namespace* are how a run becomes visible to the **leader**
and to any other host, not how a host learns about itself. Its own answer is on its own disk: the
document is authoritative, the broker's store is flushed by every vernemq release, and reading a
retained topic back to compute a metric from a file three directories away would make a local
reading depend on a round trip that a release empties. The estate view is the leader's roll-up; the per-host metric is the document.

**A manual run must therefore write the document, not only the topic.** Each `start.sh` writes its
own stage section of `status.json` as it goes, so a stage run by hand is indistinguishable to the
metrics from one supervisor scheduled — which is the property that makes the scripts genuinely
standalone rather than merely separately invocable.

| Metric | Reads, in the document | Rule | Mirrored on the topic |
|---|---|---|---|
| `host/failed_backups` (`Fail BKP`) | `stages_failed` and `stages_run` in `<run>/status.json` | `failed ÷ stages_run × 100` — `stages_run` is 2 on an `edge` host, 3 on a `server` — red if not `0` | `supervisor/<host>/backup/status` |
| `host/used_backup_space` (`Used BKP`) | `disk_usage_perc` in `<run>/tertiary/status.json` | amber above `90`, red above `95`; **errors on an `edge` host**, which owns no `/backup` and writes no tertiary document | `supervisor/<host>/backup/stage/tertiary/status` |
| `service/backup_status` (service `BKP`) | `success_bool` in `<run>/<service>/status.json` | true is healthy, which `Truthy()` already expresses | `supervisor/<host>/backup/stage/primary/service/<service>/status` |

**On an `edge` host only the primary and secondary stages run, so the metrics scope to that.**
`Fail BKP` divides by `stages_run` rather than a hardcoded 3, so two clean stages read `0` and a
failed secondary reads `50`. `Used BKP` is a statement about the backup disk, which an `edge` host
does not have — it errors into the blank-and-alert "could not measure" state, the same reading
`MetricHostAllocatedMemory` gives on a host absent from the schema, rather than reporting a
confident number about somebody else's disk. `service/backup_status` is unchanged: the primary
stage runs on every `edge` and `server` host, so each module's `success_bool` is produced everywhere.

Mapping onto the two-boolean colour model the display already uses (`pulse=false` is red,
`pulse=true` with `trend=false` is amber):

- **`Fail BKP`** — `pulseRule: Bounded(Self, Exactly, 0)` and `trendRule: Bounded(Self, Exactly, 0)`,
  which is what it declares today. Only the value changes: the stub becomes the failed-stage share,
  `stages_failed ÷ stages_run`.
- **`Used BKP`** — `pulseRule: Bounded(Self, AtMost, 95)`, `trendRule: Bounded(Self, AtMost, 90)`,
  replacing today's 90/80, so the thresholds are the ones stated above rather than inherited from a
  placeholder. **It reads the document and never the filesystem.** `/backup` is unmounted between
  runs by design, so a metric that stat'd it directly would paint the blank-and-alert "could not
  measure" state on a `server` for the twenty-three hours a day the disk is off — a permanent fault
  reporting a normal condition. The run-level `disk_usage_perc` from `<run>/tertiary/status.json` is
  the reading, the derivation names the run directory it came from and its age, and the metric errors
  when no such document has ever been read — which on an `edge` host is always, since it runs no
  tertiary stage.
- **`service/backup_status`** — `Truthy()` on both rules, replacing today's `Always()`. `Always()` is
  what makes the current stub green regardless, and it is exactly the "declaring itself healthy
  whatever it holds" pattern `host/services` was converted away from.

Each metric's `description` in `metricBuildersByID` loses its `not yet implemented` /
`always true until implemented` clause, and each keeps stating its numbers through constants on the
probe rather than as literals in two places. **`host/failed_backups` also gains `unit: "%"`**, which
it lacks today while both layouts suffix its box with `%` and every sibling failure metric —
`failed_shares`, `failed_drives`, `failed_log_messages` — declares it. That goes in with the
`Fail BCK` → `Fail BKP` label rename of item 12, since both are one-line corrections to the same
metric.

**Staleness is the probe's judgement, and it is derived rather than written.**
`backupStaleWindow` is `24h + backupRunCeiling` — **29 hours** — so the allowance for a run to
complete is the same five hours that bounds the leader's lease and the run itself, stated once in
`probe_impl_backup.go` and never as a literal at a call site. A run
directory is *current* when its timestamp is within `backupStaleWindow` of now **and** it holds a
`status.json`. When no current run exists:

- **`Fail BKP` reads `100`**, since every stage has failed to produce a result
- **`service/backup_status` reads `false`** for every module
- **`Used BKP` keeps reading the newest document it can find**, current or not, because disk usage
  does not become unknown just because a run was missed and reporting `0` would paint a confidently
  green box. Its derivation carries the document's age, so a stale number says so. It **errors** only
  where there is no document at all — a supervisor that has never seen one — which is the
  blank-and-alert "could not measure" state, exactly as an unreadable sensor produces.

There is no in-process last-value carry, and there was no need for one: the last value is on disk in
the last `status.json`, so a restart re-reads it rather than losing it. That is one source of truth
rather than two that can disagree.

**The reads are cache-period work, not per-poll work.** `status.json` changes at most once a day, so
the probe parses it on the `--cache-period` refresh and on the pulse following a run it performed
itself, exactly as `probe_lib_mounts.go` treats its snapshot. **Only the two host metrics may declare
`warming: true`** — the table's `init()` panics on a service-scoped metric that declares it, so
`service/backup_status` reports `false` before the first read rather than warming, which is also the
honest reading for a module whose backup has not been observed. The derivation names the run
directory and its age so a stale reading explains itself without a debugger.

### What this needs that does not exist yet

Prerequisites about the image and the container boundary. Note the stage scripts publish to the
broker with `mosquitto_pub` and the broker variables in `<install>/supervisor/latest/.env`, which
are already present on all five hosts — that half needs nothing new, see item **16**.

**Three packages in the image.** `docker_deps_base.txt` carries `mosquitto-clients`, `jq` and
`smartmontools` and none of these:

| Package | Needed by |
|---|---|
| a docker client | the primary stage — each module's script runs `docker exec` and `docker stop`/`start` |
| `rsync` | the secondary and tertiary stages |
| `util-linux` | `mountpoint`, the guard every stage and `mount.sh` depend on |

All three are base rather than build packages, since they run in the shipped image. Add the names,
run `fab generate`, then paste the pinned `RUN` block from `docker_deps.sh` into the `Dockerfile`.
`cifs-utils` is **not** in this list: the only samba mount left is an `edge` host's `/share/<n>`
fstab entry, which the *host* mounts — a host concern, not the image's — and a `server`'s `/backup`
is a local disk.

**Same-path mounts beside the read-only `/:/host`.** Mount the directories the driver needs at the
paths they already have on the host, so the script the driver runs is the same script, at the same
path, reading and writing the same places, whether invoked from a shell on the host or from inside
`supervisor`:

| Mount | Mode | Form-factor | Why |
|-------|------|-------------|-----|
| `/var/lib/asystem/install` | `ro` | all | each module's `backup.sh` and its `.env` |
| `/home/asystem` | `rw` | all | the module data directories, where `backup/` is written |
| `/share` | `rw` `:rshared` | all | the secondary stage's destination — a `server`'s own partitions, or an `edge` host's fstab `cifs` mount |
| `/backup` | `rw` `:rshared` | `server` only | the tertiary stage's destination, mounted by `mount.sh` inside the container |
| `/var/run/docker.sock` | `rw` | all | already mounted — `exec` into a module, and `stop`/`start` for offline copies |

**`/share` and `/backup` must be bound `:rshared`, or the mounts cross the container boundary the
wrong way.** A mount the container makes under a default private bind is invisible to the host, and —
the half that actually bites — a mount the *host* makes afterwards is invisible to the container.
Two concrete cases: on a `server`, `mount.sh` mounts `/backup` **inside** the container and the
host-side `mountpoint` guards must see it; on an `edge` host, the host's fstab mounts `/share/<n>`
**after** the container started and the secondary stage must see it. Both need
propagation, so both entries carry `:rshared` — and the host's own `/share` and `/backup`
mountpoints must be shared mounts (`mount --make-shared`, or `/` shared) for the kernel to allow it.
This is the one prerequisite that is not merely a package or a path; prove it on one `server` and on
`jen` before the tertiary stage is written.

**AppArmor must be off for the supervisor container.** `mount.sh` calls `mount(2)` from inside the
container, and Docker's default `docker-default` AppArmor profile — confirmed **enforcing** on the
amd64 hosts, `docker info` reports `name=apparmor` — denies `mount`/`umount` unconditionally, even
with `CAP_SYS_ADMIN` held (which supervisor already has, for NVMe SMART). Verified on `may`:
`docker run --cap-add SYS_ADMIN debian:12-slim … mount -t tmpfs …` → **denied**; adding
`--security-opt apparmor=unconfined` → **ok**. So `docker-compose.yml` gains
`security_opt: ["apparmor=unconfined"]` on the supervisor service. This is a real widening of an
already-privileged container (docker socket, `SYS_ADMIN`, a bind of `/`), accepted deliberately as
the cost of the container driving `mount.sh`. `seccomp` is left at `builtin` — it already permits
`mount` once `CAP_SYS_ADMIN` is present. An `edge` host's container never calls `mount`, but ships
the same compose file, so it carries the flag too and simply never exercises it.

**The memory limit goes to 512M with the other compose changes.** The container's
`deploy.resources.limits.memory` is `256M` today. The tertiary stage's `rsync -a --delete` of a
whole `/share` builds an in-memory file list proportional to the file count (media libraries are
large), and the streaming `tar`/`gzip` in a module snippet is bounded but not free. `512M` is set
blind in build-order step 4 rather than measured first — the tertiary script also iterates one
`/share/<n>` at a time rather than one big `rsync`, which caps the list size regardless of the total
tree. Revisit only if a real run's RSS approaches the new cap; an OOM-killed `rsync` is a
`--temp-dir` cleanup next run, not corruption, but it is a silent stall.

**`BROKER_TOKEN` is not in `docker-compose.yml`'s `environment:`**, though `checkexecuting.sh`
already reads it — the `${BROKER_TOKEN:+…}` form makes it connect anonymously today. If the broker
requires credentials for the tasmota command topic or for the election's own topics, that variable
has to be named there before `probe_impl_backup.go` can switch the plug or claim a lease.
Three consequences, all simplifications:

- **no prefix awareness.** A path is a path. Nothing has to know whether it is running in a
  container, and no `SUPERVISOR_MOUNT`-style rewriting is needed on a module's script. `/` is
  currently mounted at `/host` read-only, which would have forced exactly that rewriting on every
  module script
- **nothing is spawned.** The probe executes the module's script directly. The throwaway container
  earlier designs proposed is unnecessary and should not be built
- **`OFFLINE` is ordinary module logic.** A script running inside `supervisor`'s container can
  `docker stop` a *different* container without dying, so stop-copy-start needs no sidecar, no
  separate execution mode and no driver involvement

**The probes keep reading `/host`.** `probe_lib_mounts.go`, `probe_lib_logs.go`, `probe_lib_sensors.go` and
`probe_lib_install.go` all rebase through `$SUPERVISOR_MOUNT`, so the read-only root bind stays; the
four mounts above are added beside it rather than replacing it.

### How a module's script is executed

**One mode, always `${SERVICE_INSTALL}/backup.sh`.** The script runs in supervisor's container and
execs into its own container only if it needs something in there. The driver never chooses between
modes, never passes the script on stdin, and never needs a sidecar. `${SERVICE_INSTALL}` is
versioned and freshly copied each release, so the script that runs is always the current one.

**The probe applies a deadline and the script does not.** `backup_awaited` in `influxdb3` waits
forever by design — waiting is the script's job, giving up is the scheduler's — so the probe runs
each module under a `context.WithTimeout` and kills it on expiry. Nothing corrupts: the server-side
backup continues and the next run's status poll finds it. The per-module and per-stage timeouts are
constants on `probe_impl_backup.go`, and both sit under `backupRunCeiling`, which bounds the whole run
and from which `backupStaleWindow` is derived.

**A lock, so a scheduled run and a hand run cannot collide.** `install.sh`'s `run_backup` can fire at
any moment during a release, including inside the daily window. The probe holds a `flock` on the
run root for the whole run and skips with a logged reason if it is held; a module's own
`BACKUP_SKIP_HOURS` throttle is the second line of defence and makes the collision harmless rather
than merely unlikely.

## Copy rules

**Primary to secondary is additive** — `rsync -a` without `--delete` — in both shapes. Mirroring here
would propagate the primary stage's seven day window to the secondary stage, and no history longer than a
week could exist anywhere. `--link-dest` against the previous copy makes an unchanged backup cost an
inode rather than its bytes.

**The secondary stage thins, then the tertiary stage mirrors.** The probe copies from the primary stage,
applies the GFS policy to what it holds, then replicates the share to `/backup`. The secondary stage is
the only one that *decides* a backup should go; the tertiary stage deletes only as a consequence of
mirroring that decision.

**An `edge` host writing to a borrowed share copies to a disk it does not own, and that is fine.** On
`jen`, `/share/10` is `mad`'s partition reached over samba, so `jen`'s secondary stage writes into
`mad`'s share and then stops — `jen` runs no tertiary stage. `mad`'s tertiary stage replicates every
one of its own `/share/*`, including `/share/10` with `jen`'s backups sitting in it, on `mad`'s own
run. The `mountpoint` guard keeps that honest: `mad` replicates exactly the shares it has mounted.

**The tertiary stage covers every share, not just the one the secondary stage writes to.** The secondary stage
only ever touches `/share/<index>0/backup/`, but the tertiary stage replicates `/share/*` into
`/backup/share/*`, so the media and data on a host's other shares are carried by the same job.

**`--delete` everywhere, `backup/` included, and that choice decides where retention actually
bites:**

| Tertiary-stage path | `--delete` | Consequence |
|---|---|---|
| `media/`, `service/` | **yes** | a file deleted on the share disappears, which is what a mirror is for |
| `tmp/` | — | not replicated at all; scratch, and large enough to be worth skipping |
| `backup/` | **yes** | a backup the secondary stage has thinned away disappears here too, on the next run |

So **the GFS policy bounds both stages, because one policy applied at the secondary stage is mirrored
into the other**. The tertiary stage owns no retention of its own, needs no ceiling of its own, and
cannot grow unbounded — every question about how deep the history goes is answered in one place.

**What that gives up is the second copy's independence, and it is given up knowingly.** `backup/`
was excluded from `--delete` so that a mistaken or buggy thin at the secondary stage could not reach the
only remaining copy — the two could never be wrong in the same way at the same time. With the
exclusion gone they can: a bad prune propagates on the next run, and there is nothing behind it.

**That protection is restored by snapshots, not by the exclusion, and it is strictly better there.**
A read-only snapshot survives a bad prune, a bad `--exclude` and a bad root, and it covers `media/`
and `service/` — which the exclusion never did. See *Filesystem, tertiary stage*. Until snapshots
exist the estate is running with one copy of a thinned backup and no history behind it, which is a
real regression against the previous design and the reason to treat that section as the next piece
of work rather than a later one.

## Retention, secondary stage — planned

**The sparse tail lives at the secondary stage, because the tertiary stage is a mirror and a mirror cannot
thin.** Whole-share replication copies what it finds; it cannot also be the thing that keeps twelve
monthly points and discards the rest. So the secondary stage owns the policy and the tertiary stage
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
  policy, which the env-driven convention already supports; this is the one taken, see *Depth is per
  module, not per estate*
- **longer runs between fulls** — one full and many deltas, so the tail is cheap, at the cost of a slower
  restore and a larger blast radius if a link is corrupt
- **deduplication** — a `restic`/`borg` repository fed from the secondary stage, which is where its value
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
the filename suffix declares, and why the secondary stage can apply this policy without knowing which
module it is looking at. Deltas are only ever retained inside the dense window.

### Depth is per module, not per estate

**The tiers are the right shape; applying the same counts to every module is the mistake.** Five of
the six are `FULL` and small — dumps, a zip, a tar — so 23 restore points is megabytes and the depth
could be doubled without anyone noticing. Effectively the whole cost of the scheme lands on two
modules, and they are the two where a deep tail is worth least:

- **`influxdb3`** emits a new `_full` whenever the current one ages past `BACKUP_RETAIN_DAYS`, so it
  already produces roughly a full a week. The tiers then pin 4 weekly plus 12 monthly — **16 full
  copies of a continuously growing object store**, not the twelve the tension above assumes.
- **`plex`** is a `FULL` tar whose bulk is metadata and thumbnails: large, and **regenerable**.
  Twelve monthly copies of a cache is the worst ratio in the estate.

**Decided.** The estate-wide defaults stay as declared and these are the per-module overrides:

| Module | daily | weekly | monthly | Why |
|---|---|---|---|---|
| `postgres`, `mariadb`, `zigbee2mqtt`, `letsencrypt` | 7 | 4 | 12 | megabytes; the tail is free and genuinely useful — a pairing, a cert, a schema |
| `plex` | 7 | 4 | 2 | regenerable metadata, large, low value deep |
| `influxdb3` | 7 | 4 | 3 | each monthly point is a full copy of a growing store; revisit if dedup lands |

**At the deep end the useful granularity is coarser than monthly, not finer.** *Restore* already
says it for the databases: rolling one back a month discards a month of good data, so an old point
is stood up beside production and a range extracted from it. Nobody needs the 14th of March rather
than the 14th of April — they need *something from before it broke*. Twelve monthly points is
resolution the use case does not have, and three or four spread over a year would serve identically.

**With three tiers, depth and resolution are the same knob**, which is why the table above shortens
rather than coarsens. A year of history cheaply would need a fourth quarterly or yearly tier; that
is not worth the machinery for a want nobody has expressed, so the answer for the expensive modules
is a shallower tail, and a fourth tier stays available if a year of `influxdb3` is ever asked for.

**The dense tier is a window, not a count, and that interacts badly with a silent failure.** The son
tier keeps every backup inside `BACKUP_RETAIN_DAYS`, so eight days of failed backups empty it at
both stages with nothing having deleted anything wrong, and the newest weekly `_full` becomes the
floor. The primary stage is protected — `backup_pruned` always keeps the newest — while the secondary
stage's son tier has no such clause and leans on father and grandfather being `_full`. That is
correct behaviour rather than a defect, but it means **implementing `failedBackups()` buys more
recoverability than any change to these counts would**: see item **7**.

**Detection latency caps the useful depth, and nothing is looking.** A year of points only helps if
the damage is noticed inside a year — see item **10**. Until something checks, depth past a couple
of months is insurance against a claim nobody will file, so effort belongs on the detector rather
than on the tail. What the tail cannot answer for at all is that all 23 points sit in one rack on
one outlet in one building: see item **15**.

**The secondary stage must not thin blindly**, and the `_full` / `_delta` suffix is what stops it having
to guess. Dropping a `_full` destroys every `_delta` after it, so the secondary stage keeps `_full`
backups as its weekly and monthly points and retains `_delta` backups only inside the dense window.

**So the secondary stage delegates: it calls the module's own `backup.sh --prune <dir>` against the
share directory.** The stage decides the policy — which points to keep, from the GFS knobs in the
environment — and the module enacts it on backups it alone understands. A `FULL` module reuses its
default pruning against a different directory; `influxdb3` applies its own rule. No new script and
no new hook, and the probe never learns which module it is thinning.

It also falls out of the primary-stage design for free, because pruning was already an overridable
step; the only change is that it takes the directory to work on rather than assuming its own.

## Filesystem, tertiary stage — decided, not built

**Decided: `/backup` becomes btrfs, snapshotted once per run and thinned on the same GFS ladder the
secondary stage applies to files — and `Used BKP` is implemented first.** The ordering is the
decision, not a preference: snapshots defer deletion cost invisibly, a full btrfs is materially
worse than a full ext4, and the metric is the alarm that makes the scheme safe to run. Convert no
disk until `usedBackupSpace()` reads the allocation tree and reports. See *Conditions*.

**`/backup` should be btrfs, snapshotted once per run and thinned on the same GFS ladder the secondary
stage applies to files.** The tertiary stage is now an exact `--delete` mirror, which bounds it but
leaves it holding no history and no independent copy — a bad thin at the secondary stage propagates on
the next run. Snapshots are what give both back, and they give more than the old `backup/`
exclusion did, because they cover the whole share rather than one subtree of it.

Scope is `/backup` alone. `/share/<n>` stays ext4 — it is a live partition holding media, its
`PARTLABEL` layout is settled, and converting it would be a rebuild for a benefit the tertiary stage
already delivers.

### What it buys that rsync cannot

**Depth at the tertiary stage without a pruner at the tertiary stage.** A mirror has no retention of
its own, so the choice used to be an unbounded `backup/` subtree or no history at all, and *Copy
rules* has now taken the second. A snapshot dissolves the choice: the mirror stays exact and bounded
by the secondary stage's policy, and the depth lives beside it in snapshots that cost only what
changed.

**History for `media/` and `service/`, which have none at all.** Those are `--delete` mirrors, so a
file deleted or corrupted on the share reaches the only copy beyond the share at the next run and the
previous state is gone estate-wide. Snapshots are the only mechanism in this design that protects
them, and they are the bulk of the disk. That also narrows what *Gaps and decisions* puts out of
scope: media stays out of scope for **policy** while gaining a year of restore points for free.

**Integrity checking, which this document currently says it does not have.** ext4 does not checksum
data; btrfs does. A monthly `btrfs scrub` per backup volume is the periodic verification *Retention,
secondary stage* names as missing, at no design cost. With `-m dup` — the single-device default on
rotational — metadata damage is repairable and data damage is detected but not repaired. Detection
alone is the thing that does not exist today.

**A read-only snapshot is a stronger guarantee than the `--delete` exclusion it replaces.**
Excluding `backup/` protected against a mistaken thin and nothing else. A read-only snapshot
protects against a mistaken thin, a wrong `--exclude`, a wrong `<index>` and an rsync run against
the wrong root — and it is the reason the exclusion could be dropped rather than merely a
consolation for having dropped it.

### The snapshot, in sync with GFS

A snapshot is self-contained by construction, so **the full/delta distinction disappears at this
tier**. The whole reason a sparse restore point must be a `_full` is that a `_delta` cannot stand
alone; a snapshot of the volume always can. Every daily snapshot is a complete restore point for
every module, and the thinning rule collapses to *keep the newest per day, ISO week and month* with
no module knowledge and no `backup.sh` sourcing.

The ladder is the one already declared — daily 7, weekly 4, monthly 12, oldest tier wins a tie — so
at most 23 snapshots per share and fewer where the tiers overlap, and the policy reads identically
in both places.

Shape:

1. **Each `/backup/share/<n>` is its own subvolume**, so a share can be snapshotted, thinned and
   rolled back independently of its siblings.
2. **Snapshots live in a sibling `.snapshots` subvolume** — `/backup/.snapshots/share/<n>/<timestamp>` —
   never inside the rsync target, or `--delete` eventually walks into them.
3. **`btrfs subvolume snapshot -r` after step 2 of the tertiary stage, before `mount.sh down`.** It is
   atomic and sub-second, so it is a fourth step of that stage, not a stage of its own.
4. **Thin the snapshots in the same step**, by the ladder above.
5. **Snapshotting belongs to the disk's owner**, like the replication itself. `jen`'s `/backup` is
   `mad`'s over `cifs`, so `jen` snapshots nothing and `mad` snapshots on its own run — the same
   division the `mountpoint` guard already enforces.

Restore becomes `cd` into a snapshot and copy the file out: no untar, no walking `--link-dest`
trees, and the *Restore* procedures above apply unchanged to what is found there.

### What it does not buy

**Snapshots deduplicate across time, not across content.** An unchanged file is not rewritten by
rsync, so successive snapshots share it entirely — which is most of the disk. Twelve monthly
influxdb3 fulls are twelve distinct files with distinct bytes, and they cost twelve times whatever
the filesystem is. So the tension in *Retention, secondary stage* is untouched and the `restic`/`borg`
verdict stands exactly as written: not yet, revisit when the object store passes a few GB.

Worth knowing meanwhile: btrfs supports out-of-band extent deduplication, so `duperemove` over
`/backup` can collapse those fulls after the fact. That is a cheaper first move than introducing a
repository format, and it is not available on ext4.

**Deletions stop freeing space, and this is the sizing trap.** A media file deleted on the share
today frees its bytes on `/backup` at the next run. Pinned by a snapshot it stays until the last
snapshot referencing it expires — up to twelve months. Churn that currently costs nothing becomes
deferred cost, and `df` will not explain it. `btrfs filesystem usage` will, roughly; quota groups
will exactly, at a real performance price on a spinning disk, so do not enable them.

**It is not immutability.** Root can delete a read-only snapshot, so this protects against bugs and
accidents, not against a compromised host. The powered-off outlet remains the actual air gap and is
the stronger of the two.

### Conditions

**`Used BKP` must be implemented first — decided, and it is a gate rather than an ordering
preference — and on btrfs it cannot be a `statfs`.** Two reasons, and
only the second is about the filesystem. The disk is unmounted between runs, and a `statfs` of an
unmounted mountpoint succeeds while silently reporting the root filesystem — the same trap
`probe_lib_mounts.go` documents for automount shares, which is why nothing there stats an unmounted
path. So the reading has to be taken while the disk is up and carried on a snapshot, which makes it
`backupProbe`'s even though the metric is host-scoped. Then: btrfs free space depends on chunk
allocation and the profile, and snapshots pin extents `statfs` attributes to nobody, so a filesystem
can report headroom and still fail writes with `ENOSPC`. The reading must come from the allocation
tree — `/sys/fs/btrfs/<uuid>/allocation/{data,metadata,system}/{total_bytes,bytes_used}` against the
device size — which needs no `btrfs` binary and follows the sysfs habit `probe_lib_sensors.go` and
`used_network` already have. A `statfs` implementation written for ext4 would under-report silently
once snapshots exist.

This is a prerequisite rather than a follow-up, and the metric's declared bounds are already the
right alarm: the deferred-deletion creep above shows up against `AtMost 80` on the trend while the
pulse is still under 90, so it surfaces as an amber box months before the disk is a problem. See
item **7**.

**A clean unmount before the outlet is cut is load-bearing.** btrfs on a USB bridge that lies about
`FLUSH`/`FUA` is the classic way to lose a filesystem, and these are USB spinning disks on a relay.
The normal path is already safe — `mount.sh down` unmounts before the leader's destroy switches
off — but **the lease-expiry path is not**: a leader hitting `backupRunCeiling` cuts power to hosts
that may still be mid-`rsync`. On ext4 that is a fsck; on btrfs it is worse. Either have the expiry
path `sync` and attempt an estate-wide `mount.sh down` before switching off, or accept the risk
explicitly. This wants deciding before the disks are converted, not after.

**Mount options** are `noatime,compress=zstd:3`. Leave `autodefrag` off — it is the wrong trade for
a write-once archive on spinning rust.

## Boundary with Go — planned

The division moved. Go is no longer only the scheduler: it is the driver, and shell is only ever a
module's own knowledge of its own data.

| | Owns | Must not |
|---|---|---|
| a module's `backup.sh` | what is safe to copy, how to produce it, its own throttle, its own pruning, its own vocabulary | know the schedule, the stages, `/share`, `/backup`, the status document or any metric |
| `probe_impl_backup.go` | when to run, discovering the modules, ordering and timing the stages, the `/share` and `/backup` copies, deadlines, the lock, writing `status.json`, judging staleness, feeding the three metrics | inspect a data directory, choose an exclusion, parse a backup format, contain a module name, or know a device topic, an fstab line or a mountpoint |
| `probe_lib_broker.go` | broker sessions for any probe — `brokerDial` to act and disconnect, `brokerHold` for a session carrying a will, `brokerWatch` for a standing subscription read from memory | know a stage, a module, a mountpoint, a lease, an election, or what any topic it is handed means |
| `mount.sh` | the readiness wait, the fstab entries, the `mountpoint` assertions | know a module, a stage, a backup format, the schedule, the status document or the broker |

If any side reaches into another's right-hand column, the split has failed. The test for the probe
is that it contains **no module-specific line and no estate-specific literal** — no
`rack_backup_plug`, no `/share/10`, no `cifs`. It switches the plug through a topic `config.json`
gave it, and it calls `mount.sh up` and reads an exit code. The
test for `mount.sh` is that it makes no decision that depends on which host it is running on. The
test for a module script is that it still runs correctly by hand with no supervisor process
anywhere.

**Exit codes still matter**, because a module's script remains a hand-runnable program:

| | |
|---|---|
| `0` | backed up, or legitimately skipped by its own throttle |
| non-zero | failed — the probe records `success_bool: false` for that module and does not promote it |

The probe's own outcome is `status.json`, not an exit code — it is a daemon, not a command.

## Code style — planned

**A helper is earned by a second call site in a second function, and nothing else earns it.** The
rule is a trichotomy, and every step here is decided by which case it is in:

| Called from | Write it as |
|---|---|
| exactly one place | **inline** — no function, no name |
| several places, all inside one function | a **local closure**, declared beside its first use in that function |
| several functions | a **package-level helper** — this is the only case that earns one |

A function called from exactly one place is not an abstraction, it is a jump: the reader leaves the
flow, reads a name that restates the code beneath it, and comes back. This applies to
`probe_impl_backup.go` and `mount.sh` alike, and to every backup snippet — the probe should read as the
run it performs, in the order it performs it, and a snippet should read as the one command that
module actually needs.

- **Inline first.** Write the stage inline and split it only when a second *function* needs it.
  Three stages that each read straight down beat a dozen four-line helpers whose names are the only
  documentation of an order the code no longer shows.
- **A repeated expression inside one function is a local closure, never a package helper.** Declared
  beside its use, so the name is visible exactly where it means something and nothing else can call
  it. Reaching for a package-level function the moment an expression appears twice is what fills a
  package with names that each mean something in only one place.
- **Prefer repetition to a parameterised helper.** Two similar `rsync` invocations spelled out are
  easier to read, and easier to make differ, than one helper with a flag argument that both callers
  must mentally re-expand. The generation design already takes this position for the snippets —
  "repetition between snippets is preferred over parameters on the generate call" — and it holds
  inside the Go for the same reason.
- **The exceptions are the ones that already exist in this module**: a helper with genuinely more
  than one caller, and a pure function that is table-tested on its own (`driveComputed`, `driveLife`
  and the status-document parsing are the shape — a real input-to-output rule, tested rather than
  merely named).

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
path, including a crash or a kill, removing the `.tmp` and the timestamp directory if no backup
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

These are what let the secondary stage apply GFS to a module it knows nothing about: a `_full` may be
kept as a weekly or monthly point, a `_delta` only inside the dense window.

## Restore

| Module | Procedure |
|--------|-----------|
| `influxdb3` | untar the `_full` and every `_delta` after it, in order, into an empty object store — a `_delta` is meaningless without the `_full` it hangs off |
| `postgres` | `gunzip -c all_<timestamp>.sql.gz \| psql -U postgres` |
| `mariadb` | `gunzip -c all_<timestamp>.sql.gz \| mariadb -uroot -p` |
| file copy | restore the backup over the data directory, then redeploy the module so the git-managed files return |

For anything older than the primary stage's window, restoring in place is rarely right — rolling a
database back a month discards a month of good data. Stand the copy up beside production, compare,
and extract the range that matters.

HA's configuration lives in `homeassistant` but its recorder lives in `postgres`, so restoring HA to
a day needs both at that day. A single daily pass produces same-day backups minutes apart: not
transactional, but a loose estate-wide restore point, and a reason to keep every module on one
schedule rather than letting them drift onto their own. That is also why the primary stage runs
**serially** rather than in parallel — the backups are minutes apart rather than concurrent, and a
parallel run would put six modules' load on one host at once for no gain a nightly window needs.

## Gaps and decisions

**Open** means an answer is still needed from a human; **gap** means something is missing or wrong
with no question attached. Ordered by what would hurt most.

| # | Item | State | Blocks |
|---|------|-------|--------|
| 1 | No restore has ever been tested | gap | trusting any of this |
| 2 | influxdb3 keeps two copies and prunes neither | **defect — do this first** | running daily |
| 3 | The driver is not built — `probe_impl_backup.go` does not exist | gap | daily backups, the secondary and tertiary stages |
| 4 | Backups are readable on the public samba share | accepted | — |
| 5 | The tertiary stage does not exist, and the mirror keeps no history | gap, decided | off-host |
| 6 | Five modules need a script | gap | knowing this is sufficient |
| 7 | Nothing reports backup health | gap | — |
| 8 | Nothing has been sized | gap | tertiary-stage sizing |
| 9 | No automated tests | gap | — |
| 10 | Detection latency dominates retention depth | gap | — |
| 11 | A module's script has no lock | gap, minor | — |
| 12 | ~~`Fail BCK` is labelled inconsistently with its metric~~ | **done** | — |
| 13 | The cluster singleton is not built | gap | switching the outlet off |
| 14 | `mount.sh` does not exist, and mount propagation is unproven | gap | the secondary and tertiary stages |
| 15 | Every copy is in one building | gap, decided | surviving the site |
| 16 | The broker namespace needs a glob list and a liveness timestamp | gap, decided | the stage scripts |

**The next piece of work is item 2**, the only entry marked *defect* rather than *gap*: influxdb3
keeps two copies and prunes neither, so it grows without bound, and the plan already says that must
be fixed before anything runs daily. It is also the smallest of the candidates and it gates the
value of the rest — a driver scheduling runs against an unbounded store just fills the disk on a
timer.

**No judgement is left.** Every item is decided or simply not built; item 6's four `verify` rows are
closed as derived, leaving five modules that need a script written rather than a question answered.

Out of scope, deliberately: media and user data on `/share/<n>/{media,service}`, which is not
module state — though it shares the `/backup` disk and the tertiary stage, so it is out of scope for
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

**A clean start is planned: every existing backup is wiped before the next deployment.** That is a
deliberate reset rather than a fix — see *Does the wipe resolve this* below for exactly what it does
and does not close.

Introduced by moving influxdb3 onto the generated wrapper, and not yet fixed. Its snippet calls
`influxdb3 create backup` and then tars the resulting directory into `backup/`, which means:

- **the server-side set is never pruned.** Nothing calls `influxdb3 delete backup`, so
  `${SERVICE_DATA_DIR}/cluster_1/backups/` accumulates every full and delta ever taken, for ever.
  The wrapper's `backup_pruned` only reaps `backup/<timestamp>` directories — our tars — and never
  touches what the server holds.
- **every backup exists twice on disk**, once as the server's directory and once as our gzipped tar.
  The hand-written version avoided this with a hardlinked export that cost nothing.

Worse, the server-side set lands **inside `${SERVICE_DATA_DIR}`**, which is exactly why the module
contract puts backups at `<data root>/backup`, a sibling of the versioned homes: `install.sh` copies
the old home into the new one on every deploy, so every influxdb3 release drags the whole accumulated
history forward. Our tars are safely outside; the server's set is not. And all of it lands on the one
module that actually grows, which is the worst place for it.

**Verified against production on 2026-09-01, and the defect is latent rather than active.** On
`max`: `latest/cluster_1/backups` is **empty**, `/home/asystem/influxdb3/backup` **does not exist**,
and `<install>/influxdb3/latest/backup.sh` is **not deployed** — the host is running influxdb3
`10.200.1315` from 17 August, which predates the wrapper, and `run_backup` does not appear in its
deployed `install.sh` either. So nothing has accumulated because **this module's snippet has never
executed in production**. The deadline is therefore sharper than "before this runs daily" — it is
**before the next influxdb3 release**, which is what will first execute it.

**The primary stage itself has run elsewhere, so this is an influxdb3 deployment lag rather than an
estate-wide one.** The same survey found wrapper output on two hosts: `mad` holds four run
directories under `/home/asystem/plex/backup` from 18 August totalling **3.8 G**, and `jen` holds
`/home/asystem/zigbee2mqtt/backup` at 84 K. No `postgres`, `mariadb` or `letsencrypt` backups exist
yet, and `/share/*/backup` carries nothing from the secondary stage — only a hand-made
`plex-rescue` directory of 2.4 G on `/share/10`. So the primary stage works and has produced real
artefacts; what has never run is influxdb3's snippet and every later stage.

**`influxdb3 delete backup` exists and takes `--name`, confirmed on the running server.** It refuses
an in-progress backup, which the snippet already avoids by waiting through `backup_awaited`. It also
takes `--incremental`, documented as deleting the named incremental *and every child incremental
depending on it*.

**The cascade for a full is not documented and must be tested before the fix relies on it.** The
plan's proposal below says "honouring the cascade, since dropping a full drops its deltas" — that is
an assumption. The help text promises the cascade only for `--incremental`; whether deleting a
`full-*` removes its deltas, errors, or silently orphans them is unknown. Establish it on a scratch
store first, and if a full does not cascade, delete each dead chain's oldest delta with
`--incremental` before deleting its full.

**The fix is not "delete what we just tarred".** `influxdb3 create backup --incremental --parent
<name>` needs its parent to still exist server-side, so deleting the backup just captured would
strand the next delta. What is genuinely dead is every **older chain**: a restore untars our tars
into an empty store and never reads the server's set, so the server only needs the chain currently
being extended — the newest full and the deltas hanging off it. So after a successful tar, delete
every server-side backup outside the current chain with `influxdb3 delete backup`, honouring the
cascade, since dropping a full drops its deltas. That bounds the store at roughly one full plus
`BACKUP_RETAIN_DAYS` of deltas instead of everything ever taken.

#### The pruning workflow

**Where it goes: a `backup_pruned` override in the snippet, not a tail on `backup_written`.** The
wrapper already calls `backup_pruned` after a successful run and the module may redefine it, so
influxdb3 overrides it to do both halves — the wrapper's default reaping of our `backup/<timestamp>`
directories, then the server-side prune below. That keeps "prune" one verb, and it inherits the
wrapper's guarantee that a failed run never prunes anything.

**The chain is inferred from the names, because nothing records parentage.** The store holds
`full-<timestamp>` and `delta-<timestamp>` directories and no link between them, but the snippet
only ever parents a delta to the newest name — so **the live chain is the newest `full-*` plus every
name sorted after it**, and everything before that full is dead. `backup_stored` already lists and
sorts them.

Per run, after the tar has been written and renamed:

1. **Compute `keep`** — the newest `full-*` and every name after it in timestamp order. The backup
   just taken is always in `keep` by construction, so the run can never delete its own output.
2. **Compute `dead`** — everything else. Empty on most runs; non-empty only on the run that rolled
   over to a new full.
3. **Delete each dead `delta-*` newest-first**, with `--incremental`. Newest-first means the named
   backup never has a surviving child, so the cascade is always a no-op and **the undocumented
   breadth of the cascade is never relied on**. Deleting the *oldest* first with `--incremental`
   would collapse a whole dead chain in one call and is the optimisation to take later, once the
   cascade has been established on a scratch store.
4. **Delete the dead `full-*` last**, without `--incremental`, once its deltas are gone.
5. **Tolerate a name that is already absent** — the prune must be idempotent, because step 6 makes
   retries normal.
6. **A prune failure warns; it never fails the run.** The backup succeeded and the artefact is on
   disk; housekeeping that could not complete is not a lost backup, and marking it failed would
   suppress a good backup from the secondary stage. The next run retries, which is safe because the
   prune is idempotent and the dead set only grows.

That bounds the store at one chain: a full plus at most `BACKUP_RETAIN_DAYS` of deltas.

**A hole next to this one, and one condition closes it.** Parent selection trusts the *server* —
`backup_written` takes its parent from `backup_stored` and accepts it if `backup_status` is
`completed` — while restorability depends on **our tar**. A server-side backup that completes and
then fails to tar leaves the next run parenting a delta onto a full we do not hold, and every delta
from there is unrestorable with nothing reporting it.

The fix is a single eligibility test, since a server name and our directory share their timestamp:
**a server-side name may be the parent, or count as the current full, only if
`${BACKUP_INTERNAL_ROOT_DIR}/${name#*-}` exists.** One `[ -d … ]` in the loop that already walks
`backup_stored`.

Two things fall out of it, which is why it is worth preferring to a separate orphan sweep. An
ineligible newest name makes the run take a **full** rather than a delta — the safe direction, since
a full is restorable on its own. And that new full then puts the orphan outside the live chain, so
**the prune deletes it on the same run** with no extra pass. `backup_stored` itself stays unfiltered,
because the prune must see everything in order to delete it.

#### Does the wipe resolve this

**No. It clears the backlog, and item 2 is the leak.** Nothing prunes the server-side set, so
starting from empty means starting to accumulate from zero and still accumulating without bound —
one chain on day one, every chain ever taken by day three hundred. The pruning still has to be
written, and the deadline is unchanged: before the next influxdb3 release.

What the wipe genuinely does resolve:

- **no legacy format to reconcile.** `mad`'s four plex run directories and `jen`'s zigbee2mqtt
  backups predate later changes to the naming and the full/delta suffixes; wiping means the first
  run of every module writes the current shape and nothing has to read two.
- **no accumulated history dragged forward.** `install.sh`'s copy of the old home into the new one
  carries whatever is inside `${SERVICE_DATA_DIR}`, so a wipe resets that cost to zero — until the
  unpruned server-side set rebuilds it.
- **a clean baseline for item 1.** A restore test against a chain of known provenance is worth more
  than one against artefacts of uncertain age.

**One risk it creates, and it is worth spending an hour to avoid.** Wiping leaves the estate with
**no backups at all** until the first successful run of the new path — and that first run is also
the first time any of this has been exercised, since item **1** is still open. `mad`'s 3.8 G of plex
backups and the 2.4 G `plex-rescue` on `/share/10` are the only real backup artefacts that exist.
**Test a restore from one of them before wiping**, not after: it is the only opportunity to prove
the restore procedure against something that was produced by the real path, and it costs nothing but
the time, because the artefacts are being deleted anyway.

**The double-on-disk half is bounded, not removed, and that is the right answer.** Our artefact is a
gzipped tar, so the hardlinked export the hand-written version used is not available — a portable
backup is necessarily a second copy of the bytes. Pruning to the current chain caps the duplication
at one chain rather than eliminating it, which is the most that can be had while the artefact stays
portable.

### 3 The driver is not built — gap

Every module's `backup.sh` works, can be run by hand, and is called at release time by
`install.sh`'s `run_backup`. Nothing calls them on a schedule, and the secondary and tertiary stages do
not exist. The build order is the one thing this document adds, and it starts before the Go:

0. **The two prerequisites that are not Go work.** Fix **item 2** — nothing may run daily until
   influxdb3 stops keeping an unpruned second copy inside its own data directory, because running it
   daily is what makes that bite. And rehearse **item 1**, the restore, which needs no driver and can
   be done by hand today; it does not block writing any of what follows, it blocks trusting it.
1. **`--daily-time` and the gate** — `config.DefaultDailyTime`, `Periods.DailyMinutes`, the flag on
   `cmd_serve.go`, and the out-of-band daily loop in `probe.Run` calling `daily(ctx)`, started for
   `serve` alone. Testable on its own, with no backup behaviour behind it, and it is the piece
   anything else daily will reuse.
2. **`probe_impl_backup.go` and the primary stage** — the probe registered and the two host metrics moved
   off `hostProbe`, then each enrolled module serially, writing the log tree and `status.json`. Runs
   on every `edge` and `server` host. Stops there: a complete, useful daily backup with no `/share`
   involvement.
3. **The metrics** — `Fail BKP`, `Used BKP` and service `BKP` off the status document, with the
   `backupStaleWindow` rule. Depends on 2 and nothing else.
4. **The bind mounts, the packages, the memory bump and the AppArmor flag** — `/home/asystem` and
   `/var/lib/asystem/install` (all hosts), plus the docker client and `rsync` and `util-linux` in
   `docker_deps_base.txt`, and `deploy.resources.limits.memory` raised to `512M`. The `/home/asystem`
   bind and the docker client are needed before 2 runs anywhere real. The `/share` and `/backup`
   `:rshared` binds and `security_opt: [apparmor=unconfined]` are only needed by 6, and depend on the
   operator having made `/share` and `/backup` shared mounts and written each `server`'s `/backup`
   fstab line.
5. **The secondary stage** — the `rsync --link-dest` copy into `/share/<index>0/backup/` (`server`)
   or the lowest mounted `/share/<n>` from fstab (`edge`), the GFS thin by delegation. No election,
   no `mount.sh`, no `/backup` — the share is always mounted. Runs on every `edge` and `server` host.
6. **`mount.sh`, the `/backup` mount and the cluster singleton** — `server` hosts only. The readiness
   wait and fstab-driven `/backup` mount inside the container (needs the `:rshared` bind and the
   AppArmor flag, proved on one `server` and on `jen`); then `probe_mqtt.go`, the retained-topic
   mutex, the will, the five-hour lease, the narrowed `broker_topic_glob_data` and the three declared
   topics. Both independently testable — `mount.sh up`/`down` by hand, the election against a scratch
   broker with no disks.
7. **The tertiary stage** — `server` hosts only: the preamble, the `rsync -a --delete` mirror of
   every mounted `/share/*` into `/backup/share/*` with `--temp-dir`, the `mountpoint` guards, then
   `backup.sh tertiary stop` unmounting `/backup` on the way out. Gated on the election and on `mount.sh up`
   succeeding. Do not rely on this until step 0's restore rehearsal has been done: a promotion is
   worth what a restore is worth.

A per-host cron calling each `${SERVICE_INSTALL}/backup.sh` remains a reasonable interim if daily
backups are wanted before step 2 lands — it needs nothing that does not already exist.

### 4 Backups are readable on the public samba share — accepted

`storage/install_prep.sh` publishes every `/share/<n>` as `public = yes`, `read only = no`,
`create mask = 0666`, so once the secondary stage runs, database dumps — and HA's `secrets.yaml` and
`.storage/auth` when that module gains a script — are readable by anything on the LAN reaching
samba. They cannot be excluded, because a restore needs exactly those files.

**Accepted, deliberately.** The two fixes considered were moving `backup` outside the published tree
and giving it its own restricted share; both were rejected as cost without benefit at this trust
boundary. The LAN is the boundary, `jen` reaches `mad`'s share as an ordinary samba client, and the
same share already carries everything else this estate holds.

Two consequences to keep in view rather than act on. **Writable matters more than readable** —
`read only = no` means a LAN client can *delete* a backup, so samba exposure is a availability risk
before it is a confidentiality one, and it is the secondary stage's copy that is exposed while the
primary stage's copy under `/home/asystem` is not. And this is the argument that would have justified
encryption at rest, which is recorded as decided against below; if that is ever revisited, this is
the reason it would be.

### 5 The tertiary stage does not exist, and the mirror keeps no history — gap, design decided

Everything lives on the machine it protects, so a dead host loses the primary and secondary stages
together.

The shape is settled: the tertiary stage is the replication of `/share` to `/backup`, module backups
riding along in the `backup/` subtree, and **the secondary stage owns the GFS thinning** because a
mirror cannot thin. A `restic`/`borg` repository alongside it was considered and rejected at these
volumes — revisit only if the volumes ever justify it. Nothing new has to own it: whatever
replicates `/share` to `/backup` does the job, in one `--delete` pass with `backup/` included, so
the mirror is exact and the depth is the secondary stage's policy alone.

Until then, **the secondary stage has no retention at all** — the copy from the primary stage is
deliberately additive, so nothing on the share is ever deleted.

And once built, **the tertiary stage needs no ceiling of its own** — `--delete` covers `backup/` too,
so it holds exactly what the secondary stage holds. The cost is that it is no longer an independent
copy: see *Copy rules* for what that gives up, and *Filesystem, tertiary stage* for the snapshots that
give it back.

### 6 Five modules need a script — gap

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
| `rhasspy` | zzz | ❌ | no | **declared derived** — a trained voice profile would not be, so this is the one of the four carrying residual risk; retrainable from the same inputs and nothing else here depends on it |
| `openra` | max | ❌ | no | **declared derived** — settings and replays, of no operational value |
| `appdaemon` | zzz | ❌ | no | **declared derived** — apps come from git, and nothing generated is kept alongside them |
| `vernemq` | meg | ❌ | no | **declared derived** — the retained store persists on disk but is derived by design, flushed deliberately on every vernemq release and republished by every module on deploy, so there is nothing durable to copy |
| `weewx` | jen | ❌ | no | writes to the `mariadb` weewx database; configuration and skins from git |
| `wrangle` | mad | ❌ | no | writes to `postgres` |
| `network` | mad | ❌ | no | writes to `influxdb3` and MQTT |
| `tempstat` | may | ❌ | no | writes to MQTT |
| `nginx` | meg | ❌ | no | configuration generated, certificates pulled from `letsencrypt` |
| `cloudflare` | may | ❌ | no | configuration generated, credentials from the environment |
| `supervisor` | all | ❌ | **driver** | no generated script — the run record it writes daily is its backup, promoted from the standard backup root like any other |
| `mlserver` | max | ❌ | no | mounts `mlflow`'s backup root; no state of its own |
| `monitor` | zzz | ❌ | no | host paths mounted read-only |
| `unpoller` | zzz | ❌ | no | no volumes |
| `redpanda` | zzz | ❌ | no | no volumes |

**The four `verify` modules are closed as derived**, which is the decision rather than a finding —
`rhasspy`, `openra`, `appdaemon` and `vernemq` are declared out of scope with the reasoning in the
table. Three are safe on their own facts: apps from git, a broker store flushed and republished on
deploy, and game settings. **`rhasspy` is the one that carries residual risk** — a trained voice profile is not
reproducible from git, only retrainable from the same inputs — so if a profile is ever trained and
valued, this row is the one to reopen. Nothing else in the estate depends on it.

Two things this table changed. **`mlflow` was missed** by the original inventory because it holds no
`${SERVICE_DATA_DIR}` — presence of a data directory is not the same as holding state, and any
future module mounting a share needs the same second look. And **`homeassistant` is the last open
mechanism question**, now that `zigbee2mqtt` has settled the pattern for a module with a native API
and `plex` has settled the `OFFLINE` file-copy pattern.

Order of work, once confirmed: `homeassistant` (largest irreplaceable state), then `mlflow`
(silently uncovered today), then `sonarr`, `sabnzbd`, `grafana` — all three of which are the same
`OFFLINE` file-copy shape `plex` now demonstrates.

### 7 Nothing reports backup health — gap

`backupStatus()` returns a bare `true` (`internal/probe/probe_impl_services.go`), and `failedBackups()`
and `usedBackupSpace()` return `errUnimplemented` (`internal/probe/probe_impl_host.go`), so a
persistently failing backup is visible only in a log even though the measures and the Home Assistant
entities already exist. *Metric wiring* above specifies all three; it depends on item 3 step 2 and
on nothing else.

`usedBackupSpace()` has one constraint the other two do not: the disk is unmounted between runs, so
it cannot be a `statfs` on the poll tick, and on btrfs it cannot be a `statfs` at all — see
*Filesystem, tertiary stage*, where implementing it is a prerequisite rather than a consequence.

### 8 Nothing has been sized — gap

Partly answered by the tertiary-stage finding: module backups share the `/backup` disk with the media,
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
supervisor's schedule is the obvious place to hang it — a second implementer of `scheduled`, with
its own hour const, which is why the loop is generic infrastructure rather than a backup callback.

### 11 A module's script has no lock — gap, minor

Two concurrent runs of the same module's `backup.sh` inside one second would share a timestamp and race
on the same `.tmp`. **The throttle is no defence against the collision that matters**, and this is
the sharp edge of the version qualifier: a release-time `run_backup` landing inside the daily window
is precisely the case where the version has just moved, so `BACKUP_SKIP_HOURS` deliberately does
*not* suppress the second run. A `flock` on `BACKUP_INTERNAL_ROOT_DIR` in the wrapper is therefore
the whole defence rather than the backstop, and it is what makes the probe's own run lock sufficient
rather than merely likely to work.

### 12 `Fail BCK` is labelled inconsistently with its metric — gap, decided

The metric is `host/failed_backups` and every other name here is `BKP` — `Used BKP`, service `BKP` —
but both display layouts label it `Fail BCK` (`display_layout.go`). **Rename the label to
`Fail BKP`**, in the compact and relaxed layouts alike. It is a label change only: the metric name,
the topic, the column and the box geometry are all untouched, and both labels are nine characters so
no row's pre-resize width moves and `Compile`'s equal-width assertion still holds. The cost is
60-odd occurrences of mechanical churn in `display_test_layouts.go`.

**The same entry is also missing its unit.** `host/failed_backups` declares `unit: ""` while both
layouts suffix its box with `%` and the reading is a percentage of failed stages; `failed_shares`,
`failed_drives` and `failed_log_messages` all declare `unit: "%"`. Set it in the same edit — the unit
is projected into the model leaf and `describe.sh`, so leaving it blank misdeclares the measure to
both backends as well as reading inconsistently on screen.

### 13 The cluster singleton is not built — gap

The protocol is specified under *The cluster singleton* and nothing is written. It is the one piece
here with a genuine concurrency hazard, so it should be built and exercised before the secondary stage
depends on it: run four `serve` processes against a scratch broker, have them all claim at once, and
assert exactly one leads; kill the leader and assert the will clears the lease; expire a lease and
assert the next candidate claims it. All three are broker-level tests needing no disks.

Two numbers are still guesses and should be measured rather than reasoned about:
`brokerSettle`, which must exceed the broker round trip by a comfortable margin, and
`mountReadySeconds`, which is however long the drives actually take from relay close to enumerated.

The glob narrowing belongs to this item rather than to the secondary stage: until
`broker_topic_glob_data` is `supervisor/${SUPERVISOR_HOST}/data/#` and the three topics are declared
in `metric.Topics()`, every `fab schema` reports them as drift and aborts at supervisor, and a
supervisor release sweeps a lease another host is holding.

### 14 `mount.sh` does not exist, and mount propagation is unproven — gap

The script is specified above and nothing is written. It runs on `server` hosts only, and its whole
subject is the local `/backup` disk. Two things to prove first, both about the container boundary:

- **The `:rshared` bind.** A `/backup` mount `mount.sh` makes inside the container must be visible to
  the host-side `mountpoint` guards, and on an `edge` host the host's fstab-mounted `/share/<n>` must
  be visible inside the container. Both need `:rshared` on the bind and a shared mount on the host
  side (`mount --make-shared`). Prove it on one `server` and on `jen`.
- **AppArmor.** Confirmed enforcing on the amd64 hosts (`docker info` → `name=apparmor`,
  `docker-default` applied to the running supervisor container), and it denies `mount(2)` even with
  `CAP_SYS_ADMIN`. Verified on `may`: a `--cap-add SYS_ADMIN` container is denied `mount -t tmpfs`,
  and `--security-opt apparmor=unconfined` allows it. So the supervisor service carries
  `security_opt: ["apparmor=unconfined"]`. The rejected alternative was running `mount.sh` on the
  host via the install tree, which reintroduces the "a container cannot execute a host script"
  problem the same-path mounts exist to remove; unconfining the container is the accepted cost.

`jen`'s fstab is yours to write and this plan assumes one entry: `/share/10` as `cifs` and
automatic. `jen` has **no** `/backup` entry — it runs no tertiary stage. Each `server`'s fstab needs
a `/backup` `noauto` entry for its local disk; the script reads whichever it finds, so a different
shape changes nothing in the Go and nothing in this document beyond the table.

**Two host-provisioning steps are operator-owned, done by hand — not a module's job.** The `:rshared`
binds need the host's `/share` and `/backup` mountpoints to be **shared mounts** (`mount
--make-shared`, or `/` shared), and each `server` needs a `/backup` `noauto` fstab entry for its
local disk. Both are set by hand at host provisioning, the same way `jen`'s `/share/10` fstab line
already is — deliberately kept out of `storage`/`_debian` so the estate's mount topology stays
something a person decides rather than something a deploy silently changes. The tertiary stage is
dead until both exist on every `server`; that is a provisioning checklist item, not a code gap.

**`/home/asystem` as an `rw` bind is a real escalation — accepted.** Today the container's only host
view is `/:/host:ro`. Binding `/home/asystem` read-write gives a supervisor bug or a compromise
write access to every service's data directory on the host. Narrowing it — a `ro` bind of
`/home/asystem` for reading module `backup/` trees plus a single `rw` bind of the supervisor run
directory — was considered and rejected: it trades the "a path is a path, no prefix awareness"
property for one saved capability, and the container is already the most privileged in the estate
(unconfined, docker socket, `SYS_ADMIN`, `SYS_RAWIO`). The one bound that does hold is that the
same-path bind is `/home/asystem` and not `/`, so `/etc`, `/root` and the other hosts' install
trees stay out of reach.

### 15 Every copy is in one building — gap, decided

**Depth is the cheap axis and it is nearly maxed; independence is the expensive one and it is zero.**
Three stages, 23 restore points and a year of history all sit in one rack, on one switched outlet,
in one house. Fire, theft, a surge or a mistaken `rm` with enough reach takes every stage at once,
and no retention count changes that. Listed last because it is the newest, not because it is the
smallest — measured by what it protects against, it ranks with item **1**.

**Decided: the offsite tier carries the four small `FULL` modules and nothing else** —
`postgres`, `mariadb`, `zigbee2mqtt`, `letsencrypt`. A few hundred MB between them, they compress
well, and they are the state that genuinely cannot be regenerated. `plex` and `influxdb3` are the
expensive ones and the ones a rebuild could survive, so scoping to the first four is a rounding
error in bandwidth and covers most of what a site loss would actually cost. It is worth more than
every monthly point currently kept.

Deliberately not specified here: where it goes and what encrypts it. Both are decisions rather than
gaps, and neither should be made by extending the secondary stage — the offsite copy wants to be pulled
from the secondary stage by something with its own credentials, so that a host compromised badly enough
to destroy its own backups cannot reach the remote one. That property is the whole point and is
easy to lose by implementing it as a fourth `rsync` on the same run.

### 16 The broker namespace needs a glob list and a liveness timestamp — gap, decided

*Stage scripts and the broker namespace* can be declared and managed like every other retained
topic. Three things stood between the specification and a working one; one of them turned out to be
already solved.

**`broker_topic_glob_data` must accept a list** — a library change in
`asystem/schema/dialects/vernemq.py`, not a supervisor one. It is one string today, driving
validation, the `broker.sh sweep` and the operator scripts' filters, and
`supervisor/cluster-all/backup/#` cannot be expressed alongside `supervisor/${SUPERVISOR_HOST}/#` in a
single glob. Widening to `supervisor/#` would make one host's release sweep every other host's
topics, so it is not a shortcut available here. The change is contained: the validation already
loops per column, `describe`/`query`/`verify` already take a `globs` list, and only
`publish_script` assumes a scalar.

**A host-side script reaches the broker directly, and everything it needs is already there** —
**closed**, verified rather than assumed. `mosquitto_pub` is at `/usr/bin/mosquitto_pub` on all five
hosts (`mad`, `max`, `may`, `meg`, `jen`), and `BROKER_HOST`, `BROKER_PORT` and `BROKER_TOKEN` are
all present in `<install>/supervisor/latest/.env`, which is the same file `probe_lib_install.go` already
reads. So a stage script sources that `.env` and publishes, with no new package, no new secret path
and no dependency on the container. That last part is the point: publishing through
`docker exec supervisor mosquitto_pub` was the alternative, and it would have made a backup script
depend on the container it exists to outlive — useless in exactly the case the scripts are for, a
host whose supervisor is broken.

**A script cannot hold a last will, so liveness has to be published.** `mosquitto_pub` connects,
publishes and disconnects, so a stage killed with `SIGKILL` leaves `running` retained with nothing
to clear it. `expires_ts` in the payload is the answer specified above — the same mechanism the
lease already uses — but it means every long-running stage must refresh it on a cadence rather than
publish once at the start, and the leader must treat expiry as authoritative over `state`. The
alternative, a long-lived `mosquitto_pub -l` holding `--will-topic`, was rejected: it keeps a pipe
and a background process alive for the length of a five-hour run to save a periodic publish.

### Closed during design and build

- **Powering and mounting** — a supervisor-owned `mount.sh`, generated via `write_container_mount()`
  in this module's own `generate.py` like every other shipped script, phased `up`/`down`, driven by `/etc/fstab` rather than by a host
  list, and run on `server` hosts only (its whole subject is the local `/backup` disk). The probe
  calls it and reads an exit code, so no device name, mountpoint or filesystem type reaches the Go.
  The plug itself is switched from Go through `probe_mqtt.go`, on a topic `config.json` supplies for
  `server` hosts only, so the script never touches the broker and the driver still holds no estate
  literal.
- **Who switches the outlet off** — a leader elected daily over MQTT with a retained-topic mutex, a
  last will and a five-hour lease, running power-on as its init and power-off as its destroy. The
  primary stage sits outside it entirely, so a failed election costs a promotion and never a backup.
- **Interrupted copies** — `--temp-dir` on every `rsync`, wiped before each stage, with `--partial`
  and `--inplace` both rejected. A hard reset costs one file's transfer and leaves nothing a later
  run could mistake for data.
- **`hot` / `warm` / `cold`**, then **`module` / `share` / `backup`** — both retired in favour of
  `primary` / `secondary` / `tertiary`, one word per stage, used identically in the prose, the JSON,
  the log file names and the Go. Destination naming read well in the stage table and badly
  everywhere else: all three words were already load-bearing for something else — `module` for a
  repo module, `share` for `/share/<n>`, `backup` for the subject, the `/backup` disk, `backup.sh`
  and the `backup/` subtree — so a sentence naming both a stage and its subject collided with
  itself, and `stage.module.module` was the JSON that proved it. Tier naming carries the ordering
  instead, which is the property every rule about the stages actually turns on.
- **Supervisor's own `backup.sh`** — retired, and so is the supervisor module backup that replaced
  it. The driver is `probe_impl_backup.go`; supervisor is not enrolled through `write_container_backup()`,
  takes no primary-stage step of its own, and its run record *is* its backup, written into the standard
  backup root and thinned by date on the same tiers as everything else.
- **Where the driver lives** — `internal/probe/probe_impl_backup.go`, registered like any other probe,
  owning `host/failed_backups` and `host/used_backup_space` while `servicesProbe` keeps
  `service/backup_status` and reads its snapshot. A driver outside the probe set could not own a
  metric at all: `verifyProbes()` panics unless every metric ID has exactly one.
- **How the daily run is scheduled** — an out-of-band loop started by `probe.Run` for `serve` alone,
  calling `daily(ctx)` on its own goroutine. Not a flag on the poll tick: `onPulse` runs inline on the
  ticker goroutine, so a run threaded through it would stall every probe on the host for hours.
- **The election's topics and its client** — declared in `metric.Topics()` and moved outside the
  swept namespace by narrowing `broker_topic_glob_data` to `supervisor/${SUPERVISOR_HOST}/data/#`,
  spoken to by supervisor's own short-lived `probe_mqtt.go` rather than by the engine's session,
  which cannot carry the lease's last will and which `probe` must not import.
- **What `Used BKP` reads** — the newest `status.json` and never the filesystem, since `/backup` is
  unmounted between runs by design and stat'ing it would report a permanent fault for a normal
  condition. No in-process carry: the last value is already on disk in the last document.
- **Release-time triggering** — not retired, relocated. Per-module `install_prep.sh` hooks are gone
  and the root `install.sh`'s `run_backup` is the single release-time call site, complementary to
  the daily run rather than competing with it.
- **Encryption at rest** — decided against. Backups stay in the clear at every stage. That also
  removes the one argument that would have justified `restic`/`borg` at current volumes, so the
  tertiary stage stays a plain mirror. Item 4 is the standing reason this might be revisited.
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
  `backup_is_delta` let the secondary stage apply GFS to a module it knows nothing about.
- **Share index** — the sixth field of `.hosts`, read by `_get_host_index()`, emitted into
  `config.json`.
- **How a container runs a host script** — same-path bind mounts, `:rshared` on `/share` and
  `/backup`, and `security_opt: [apparmor=unconfined]` on the supervisor service so `mount.sh` can
  call `mount(2)`. The sidecar proposal and the host-side-`mount.sh` fallback are both withdrawn.
- **Which stages a host runs** — its `.hosts` form-factor. `server` runs all three and owns
  `/backup`; `edge` runs primary and secondary only, onto a borrowed always-mounted share, and never
  touches the backup disk or the election; `client`/`network`/`ignore` do not run `serve`. Driven off
  the same field `generate.py` already uses to decide the `config.json` schema, so no host is named
  in the Go.
- **`OFFLINE` execution mode** — not a driver concern; a script in supervisor's container can stop a
  different container without dying.
- **`zigbee2mqtt` mechanism** — its bridge API over MQTT.
- **A `.sha256` sidecar** — rejected; every backup is `.gz` or `.zip`, whose formats already carry
  CRC32, so `gzip -t` detects corruption without a second file to keep in step.
- **A report file for the primary stage** — still rejected *for a backup*: a backup's existence at
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

## Deviations (implementation log)

Recorded as the plan is implemented. Each entry: what the plan said, what was done instead, why.

### Step 1 — `--daily-time` and the daily gate — built

- **`probe.Run` signature.** Plan: "the daily goroutine is started by the serve path alone" while
  also "started by `probe.Run`". Implemented by adding a `runDaily bool` parameter to
  `probe.Run(ctx, runDaily, onPulse)` — `engine.RunAllProbesPublishLoop` (serve) passes `true`,
  `RunListeningProbesLoop` and `RunAllProbesOnce` pass `false`. The gate loop is `runDailyGate` in
  the new `internal/probe/probe.go`; the fire/seed decision is split into the pure
  `dailyGateSeed` / `dailyGateFires` and table-tested in `probe_daily_test.go`.
- **No new `scribe.Action`.** The gate-fired line logs at INFO through `scribe.ActionStart` with
  verb `schedule` (the 8-character verb rule forced the word — `elapsed`/`daily` are 7/5). The
  once-per-startup "watching [N] min daily gate" line is DEBUG.
- **`watch` has no `--daily-time` flag.** `makePeriods` gained a `dailyTime` parameter;
  `cmd_watch.go` sets `opts.dailyTime = config.DefaultDailyTime` before calling it, since the daily
  gate never starts on the watch path. `cmd_serve.go` adds `-D/--daily-time` defaulting to
  `config.DefaultDailyTime` ("01:00"), and a `periodic [N] min daily` startup line.
- **`config.Periods` gained `DailyMinutes int`**; `config.DefaultDailyTime` sits in the same const
  block as `DefaultPollPeriod`. Parsing is `toDailyMinutes` in `cmd/cmd.go` — an unparseable value
  is a startup error `invalid daily time [%s], must be HH:MM local`.

### Steps 2–3 — `probe_impl_backup.go`, metric wiring — built (Go), stage scripts pending

- **New probe `backupProbe`** in `internal/probe/probe_impl_backup.go`, registered in `probe.go`'s
  `init()` beside `servicesProbe`/`hostProbe`. It owns `MetricHostFailedBackups` and
  `MetricHostUsedBackupSpace`, which were removed from `hostProbe` (`metrics()`, the two
  `*stats.IntStats` fields, their `NewIntStats` lines, their tasks, and the two
  `errUnimplemented` stub methods). New `scribe.Source` value `SourceProbeBackup` → `probe[backup]`.
- **`service/backup_status` stays in `servicesProbe`.** `p.backupStatus(name)` now reads
  `backupProbeInstance.moduleSuccess(name)` — `backupProbeInstance` is a package var set in
  `newBackupProbe()`, the same cross-probe pattern `installReader` uses. Rule changed `Always()` →
  `Truthy()`.
- **Metric declarations** (`metric_build.go`): descriptions lost their "not yet implemented" /
  "always true until implemented" clauses; `MetricHostUsedBackupSpace` bounds moved to
  `UsedBackupPulseLimit` (95) / `UsedBackupTrendLimit` (90) constants in the shared const block;
  both host metrics gained `warming: true`. `host/failed_backups` already carried `unit: "%"` and
  both layouts already read `Fail BKP` — **item 12 was already done in the repo**, so no display or
  golden-test change was needed.
- **Staleness** (`probe_impl_backup.go`): `backupRunCeiling` = 5h, `backupStaleWindow` = 24h + ceiling =
  29h, `backupStageTimeout` = 3h — constants, not literals. `failedBackups()` reads
  `stages_failed / max(stages_run,1) * 100` from `<newest run>/status.json`, or **100** when no
  current run exists (within the window and holding a document). `usedBackupSpace()` reads
  `disk_usage_perc` from `<run>/tertiary/status.json` — newest available even if stale — and
  **errors (`errEnvironment`)** when no tertiary document has ever been written, which on an `edge`
  host is always. `moduleSuccess()` returns `(false,false)` outside the staleness window.
- **`daily(ctx)`** runs the stages serially by form-factor — `primary`, `secondary`, then
  `tertiary` when `config.HostIndex(host)` reports an index (server). It `flock`s
  `<root>/.lock` (non-blocking, skips if held), allocates the `run_id` timestamp, `exec`s
  `/asystem/etc/backup.sh <stage> start <run_id>` under `backupStageTimeout` teeing to
  `<run>/logs/<stage>.log`, calls the stage's `stop.sh` and stops the run on failure, then writes
  `<run>/status.json`. **DEVIATION vs plan:** the run-level roll-up is currently minimal — it does
  not yet read per-stage `status.json` files to aggregate `file_count`/`size_mb`, and it does not
  publish any broker topic (that is `probe_mqtt.go`, step 6). The stage scripts themselves
  (`backup/{primary,secondary,tertiary}/{start,stop}.sh`) do not exist yet — until they are
  generated (next), `daily()` treats a missing script as a stage failure and logs it. `config`
  gained `configServices.Index *int` plus `HostIndex` / `SchemaHost` accessors.
- **Not regenerated:** `fab generate` was not run (needs the full toolchain and a reachable
  InfluxDB for discovery), so `src/build/resources/schema/**` still carries the old metric
  descriptions. Re-run `fab generate` in `src/all/supervisor` and review the diff.

### Step 4 — image, compose, packages — built (code), Dockerfile pins pending

- **`docker-compose.yml`**: memory `256M` → `512M`; `security_opt: [apparmor=unconfined]` added;
  `BROKER_TOKEN` added to `environment:`; four binds added — `/var/lib/asystem/install:ro`,
  `/home/asystem:rw`, and `/share` + `/backup` in long-form with
  `bind: {propagation: rshared, create_host_path: true}`.
- **`docker_deps_base.txt`**: added `rsync`, `util-linux`, `docker.io`. **DEVIATION:** the plan says
  "a docker client"; Debian bookworm has no `docker-cli`, only `docker.io` (which also pulls the
  daemon and containerd — ~300 MB). Revisit with a slimmer source (static `docker` binary, or
  `docker-ce-cli` from Docker's apt repo) if image size matters.
- **DEVIATION — Dockerfile not updated.** `docker_deps.sh` cannot be run here (needs Docker), so the
  pinned `RUN` block in `Dockerfile` still installs the old package set. Run `fab generate` in
  `src/all/supervisor` then `./docker_deps.sh` and paste the new block.

### Stage scripts + `mount.sh` — generated, unverified

- **New generators** (written into the shared `container.py`, since moved into
  `supervisor/generate.py` — see the deviation below): `write_container_mount()` and
  `write_container_backup_stages()`, following the `write_container_healthchecks()` shape (banner,
  fragment at `src/build/resources/…`, stub written if absent, output under
  `src/main/resources/image/`, executable bit). `supervisor/generate.py` calls both.
- **Fragments authored**: `src/build/resources/mount.sh` (`mount_up`/`mount_down` — fstab-driven
  `/backup` readiness wait, mount, assert), and `src/build/resources/backup/<stage>/{start,stop}.sh`
  defining `stage_start`/`stage_stop`. The generated wrapper adds the run-directory plumbing, the
  `backup_publish` (`mosquitto_pub`) helper, `backup_guard_mounted`, `backup_stage_document`
  (writes `<run>/<stage>/status.json` atomically and publishes the topic), and manual-run detach.
- **`config.json` `backup` block**: `generate.py` writes `asystem.backup.{command_topic,state_topic}`
  = the `rack_backup_plug` cmnd/stat POWER topics. **DEVIATION:** always emitted (config.json is one
  file shared by all hosts via `$SUPERVISOR_HOST` substitution — it cannot be per-host); the probe
  keys tertiary-stage participation on `config.HostIndex(host)` (server = has an index) instead of
  on the block's presence. `config.go` gained `configBackup` and `BackupCommandTopic()` /
  `BackupStateTopic()`.
- **DEVIATIONS in the stage scripts vs the plan's full spec** (all shellcheck-clean, none exercised
  against a real host):
  - **secondary GFS is dense-window only.** It delegates thinning to each module's
    `backup.sh --prune <sharedir>`, which applies `BACKUP_RETAIN_DAYS`. The weekly-4 / monthly-12
    grandfather-father-son tiers from *Retention, secondary stage* are **not implemented** — needs a
    real GFS pruner (in the wrapper's `backup_pruned` or a new `backup.sh --prune-gfs`), plus the
    per-module `<MODULE>_BACKUP_KEEP_*` overrides.
  - **tertiary snapshots not implemented.** No `btrfs subvolume snapshot`, no `.snapshots` tree, no
    snapshot thinning — `/backup` is treated as a plain rsync `--delete` mirror. *Filesystem,
    tertiary stage* is untouched.
  - **plug power is one-directional and best-effort.** `backup/tertiary.sh` publishes `ON` to the
    command topic and calls `mount.sh up`; it does not read the state topic back. Switching **off**
    (the leader's job) is not implemented anywhere yet — see the singleton section.
  - **no election / leader / lease.** Every server runs its own tertiary stage independently; the
    outlet is never switched off. `probe_mqtt.go` and the singleton are still to build.
  - **manual-run detach** uses `nohup … & disown` gated on a tty, not a full re-exec/`tee` to both
    stdout and the log as the plan describes.

### Item 16 + backup topic declarations — built (library + Go), unverified by `fab generate`

- **`broker_topic_glob_data` now accepts a string or a list** in `asystem/schema/dialects/vernemq.py`
  via `_glob_list` / `_glob_match_any`. `_validate_globs`, `_declared_topics` and the
  `describe`/`verify` glob set all use the any-match form; every existing scalar caller
  (`weewx`, `storage`, `tasmota`, `network`, `tempstat`, `monitor`) is unaffected.
- **New option `broker_topic_glob_verify`** (`SchemaBrokerOptions.topic_glob_verify`, param
  `broker_topic_glob_verify` on `write_schema_broker`) — a list of globs that a declared topic may
  match **for verification/describe only**, never for the xlsx-column validation and never for the
  `broker.sh sweep`. This is how "declared but not swept" is expressed. **DEVIATION vs plan**, which
  implied one list threaded everywhere; splitting swept-vs-verified is what actually keeps a lease
  another host holds alive across a supervisor release.
- **`publish_script`** now emits one `-t "<glob>"` per swept glob (`glob_data_args`), defaulting to
  `-t "#"` if the list is empty.
- **`supervisor/generate.py`**: `broker_topic_glob_data` narrowed to
  `[data/#, command/#, status]` (covers every currently-declared metric/command/availability
  topic); `broker_topic_glob_verify = [backup/#, cluster-all/backup/#]`. `broker_entities` per-host
  bindings gained `STAGE` (the three reserved words) and `MODULE` (that host's services that ship a
  `src/build/resources/backup.sh`, from a `glob`).
- **`metric.Topics()`** appends the five backup templates; **`metric.Payloads()`** appends three
  `state` payloads with `match` globs — `*/backup/election`, `*/backup/status`, `*/backup/*/status`
  — the metric state payload stays matchless so `payload_for` still falls through to it. The
  glob/binding/payload-selection logic was validated with a standalone harness against the real
  host/service lists; **`fab generate` / `fab schema` have not been run**, so this is unverified
  end to end.

### Comment style — reduced to per-stage header contracts

Per feedback: the generated `start.sh`/`stop.sh` keep one engine.go-style header block only, and it
is now **stage-specific** — a `primary:` / `secondary:` / `tertiary:` block stating exactly what
that stage does (module iteration; `rsync --link-dest` to the share + GFS delegation; `mount.sh up`
+ `--delete` mirror + btrfs snapshot + `mount.sh down`), plus a per-stage `stop:` line naming its
teardown. All inline per-function comments in the fragments and wrappers were removed (fragments
carry **zero** comments). New Go (`probe_impl_backup.go`, `probe_mqtt.go`, `probe.go`) carries
**zero** comments. `container.py` and the influxdb3 snippet trimmed to 1–2 lines.

### `mount.sh` scope tightened

`mount_targets` matched fstab lines by `$2 ~ /^\/backup/` — now `$2 == "/backup"` or
`$2 ~ /^\/backup\//`, so a stray `/backupfoo` fstab entry can never be caught by `mount.sh down`.
`/share/<n>` was never in scope. Confirmed: no `stop.sh` unmounts a share —
`primary`/`secondary` only `pkill`, `tertiary` also runs `mount.sh down` which is `/backup`-only.

### Comment style — per-stage header contracts only

Per feedback: the only comments in the generated `start.sh` / `stop.sh` / `mount.sh` are the
engine.go-style header contract — a one-line summary, a **stage-specific** `primary:` /
`secondary:` / `tertiary:` block stating what that stage does, per-stage `start:` / `stop:` lines,
and `Notes:` bullets. Everywhere else the comments are gone: the fragments carry **zero**, the
`backup.sh` wrapper's `backup_pruned_gfs` and the influxdb3 snippet's added functions carry
**zero**, `BACKUP_TIMEOUT_HOURS_DEFAULT` carries none, and the new Go
(`probe_impl_backup.go`, `probe_mqtt.go`, `probe.go`) carries **zero**, per the repo-wide
no-Go-comments rule. The reasoning that was in those comments lives in this deviation log.

### Retention knobs are wrapper variables, not generate params — confirmed correct

The plan is explicit (*Module contract*, *Closed during design* → "Per-module env vars"): backup
policy values are **wrapper variables read as `${VAR:-default}` after the module `.env` is sourced**,
never `write_container_backup()` parameters, because a generate param cannot be overridden by an
operator per run (`BACKUP_KEEP_MONTHLY=2 ./backup.sh`) nor set per module in `.env_all`. So
`BACKUP_KEEP_DAILY` / `_WEEKLY` / `_MONTHLY` correctly follow `BACKUP_RETAIN_DAYS` /
`BACKUP_SKIP_HOURS`. `write_container_backup()` stays parameterless.

### Tertiary btrfs snapshots + leader roll-up — built blind, untestable here

- **`backup/tertiary.sh`**: after the rsync mirror, `backup_snapshot` takes a read-only
  `btrfs subvolume snapshot` of each `/backup/share/<n>` that is its own subvolume into
  `/backup/.snapshots/share/<n>/<run_id>`, then `backup_snapshot_thin` keeps newest-per-day (7),
  -week (4), -month (12) and `btrfs subvolume delete`s the rest. **Inert on ext4** (guards on
  `btrfs subvolume show`), which is the intended state until `/backup` is converted.
- **`Used BKP` on btrfs**: `backup_btrfs_usage /backup` reads
  `/sys/fs/btrfs/<uuid>/allocation/{data,metadata,system}/bytes_used` against the summed device
  sizes; the tertiary stage uses it for `disk_usage_perc` and falls back to `df` on ext4. The Go
  `usedBackupSpace()` still just reads that number out of `<run>/tertiary/status.json` — unchanged.
- **`btrfs-progs`** added to `docker_deps_base.txt` (snapshot creation runs in the container).
- **Leader roll-up + lease refresh** (`probe_impl_backup.go`): `refreshLease` re-publishes the election
  lease with a fresh 5h `expires_ts` after each stage; `publishLeaderStatus` writes
  `supervisor/cluster-all/backup/status` (`state`, `power_bool`, `hosts_expected/reported/failed`) at run
  start, on each `finishLeadership` poll, and terminally (`complete`/`failed`/`timeout`) before the
  lease and status topics are cleared.
- **Still untested** against a real broker or a btrfs disk. `fstab` mount options
  (`noatime,compress=zstd:3`, `autodefrag` off) are a provisioning note, not scripted.

### Stage scripts are plug-unaware; supervisor owns the plug — DEVIATION

Plan (*Powering and mounting*) has `backup/tertiary.sh` publish `ON` for itself so a manual run
needs no leader. Changed: **no stage script touches the broker plug**. `probe_impl_backup.go`'s
`powerBackupDisk("ON")` runs at the head of `daily()` on every server (idempotent), and the leader
/ reaper publishes `OFF`. `mount.sh up` still waits for the device to appear, so a fully-manual
tertiary run just needs the operator (or a running supervisor) to have powered the disk — an
acceptable narrowing, since a manual run with supervisor down is already an edge case. The stage
scripts publish only their own `status` topics.

### `/share/<n>` mounted on demand

If a `/share/<n>` a stage needs is not mounted it is now mounted from fstab.
`backup_ensure_mounted <path>` (stage wrapper): `mountpoint -q` → else `mount <path>` (with an
`ls` fallback to trigger an `x-systemd.automount`) → re-assert. `backup/secondary.sh` uses it for
its share destination (an edge host's cifs `/share/<n>`); `backup/tertiary.sh` runs it over every
fstab `/share/<n>` line with a **local** fstype before enumerating, so a server mounts its own
shares if a reboot left them down but never a cifs entry.

### `BACKUP_TIMEOUT_HOURS` + heartbeat + reaper — built, unverified

Not in the plan; added so a large first sync can be kicked off by hand without supervisor killing it,
while supervisor still ends a dead run and still powers the disk down on completion.

- **`BACKUP_TIMEOUT_HOURS`** — numeric, default `3`, `0` = uncapped. Follows the
  `BACKUP_RETAIN_DAYS` / `BACKUP_SKIP_HOURS` convention. **One source of truth:**
  `container.py`'s module constant `BACKUP_TIMEOUT_HOURS_DEFAULT` — rendered as `${VAR:-3}` into
  the `backup.sh` wrapper and the stage wrapper, and written into `config.json`
  (`asystem.backup.timeout_hours`) by `generate.py` so the Go reads it via
  `config.BackupTimeoutHours()` with **no literal of its own**. `backup/primary.sh` passes it into
  each module `backup.sh` env.
- **Graceful stage timeout** (`probe_impl_backup.go` `runStage`): `context.WithTimeout` only when
  `> 0`; `cmd.Cancel` sends SIGTERM (the stage wrapper traps it → `stage_stop`), `cmd.WaitDelay`
  = `backupStageKillGrace` (2 min) then SIGKILL. The old fixed `backupStageTimeout` constant is
  gone.
- **Heartbeat** (stage wrapper): a background `backup_heartbeat` re-stamps
  `<run>/<stage>/status.json` (new `expires_ts` field) every `BACKUP_HEARTBEAT_REFRESH` (600 s)
  with `now + BACKUP_HEARTBEAT_GRACE` (3600 s — loose, for multi-GB single files). Past
  `BACKUP_TIMEOUT_HOURS` it stamps a past `expires_ts` and exits. At `0` it stamps forever while
  alive → never timed out, only crash-detected.
- **Detach** now triggers on a tty **or** `BACKUP_TIMEOUT_HOURS=0`, so
  `BACKUP_TIMEOUT_HOURS=0 backup.sh tertiary start` backgrounds+disowns from any shell.
- **Reaper** (`backupProbe.reap`, on the existing 1-minute daily-gate ticker, server hosts only):
  1. local — if this host's newest `<run>/tertiary/status.json` is `running` with a past
     `expires_ts`, run local `backup.sh tertiary stop` and mark it `timeout`.
  2. estate — connect, read the plug `state_topic` + `supervisor/+/backup/stage/tertiary/status` +
     the lease. If the plug is `ON`, no unexpired lease is held, and no tertiary run has a fresh
     `expires_ts` for **`reaperIdleTicks` (2)** consecutive ticks (~2 min), run a one-shot
     election; the winner publishes `OFF` and clears the lease. Skipped while this host's own
     `daily()` holds `dailyRunning`.
- **Payload**: `expires_ts` added to the stage/host `status.json` shape (already declared in
  `metric.Payloads()` as `expires_ts`). **DEVIATIONS**: the reaper opens one short-lived broker
  connection per minute per server; `reap` is not unit-tested (needs a broker); a run in
  uninterruptible `D` state is not killable by SIGTERM or `pkill` — only the Go SIGKILL after
  `WaitDelay`, and only if the process is responsive.

### Tertiary stage mirrors only locally-owned shares — hardened

A server mounts other servers' shares over cifs/nfs for read access (verified on `may`:
`/share/10 20` are cifs, `/share/40` nfs4, only `/share/30 31 32` are its own). The tertiary stage
must mirror **only the shares this host owns**, and must never write to `/backup` when nothing is
mounted there (that silently fills the root filesystem). Defences:

- **`backup_local_shares`** enumerates from the kernel via `findmnt -rn` (not `/etc/fstab`, which
  lists the cifs mounts too) and keeps a mountpoint only if it matches `^/share/[0-9]+$` **and** has
  a local fstype (`ext4|xfs|btrfs|f2fs`) **and** a `/dev/*` source. Tested against a mocked `may`
  mount table → yields exactly `/share/30 31 32`.
- **`backup_disk_ready`** asserts `/backup` is a `findmnt -M` mountpoint of a local fstype with a
  `/dev/*` source before the loop starts; the loop then re-checks `mountpoint -q /backup` and
  `mountpoint -q "${share}"` immediately before every `mkdir`/`rsync`, and aborts the stage if
  `/backup` vanishes mid-run.
- `.rsync` temp dir cleared with `find -mindepth 1 -delete` rather than `rm -rf .../*`; `rsync` gets
  `--` before its paths. `backup_snapshot` now also gates on `backup_disk_ready`.
- **Propagation**: `may` reports every mount `shared` already (systemd default), so
  `mount --make-shared` is **not needed** — check each host with `findmnt -o TARGET,PROPAGATION /`
  but expect the same. Only the `/backup noauto` fstab entry is required.

### Item 13 — `probe_mqtt.go` + the cluster singleton — built (Go), unverified (needs a broker)

- **`internal/probe/probe_mqtt.go`**: `brokerClient` — a short-lived paho session (clean session,
  `SetAutoReconnect(false)`, `mqttTimeout` 5s), **not** engine's session. `dialBroker` (optional
  will), `publishRetained`, `readRetained(window, filters…)` (subscribe → sleep → unsubscribe,
  keyed by exact topic), `close`.
- **`electBackupLeader(configPath, host, runID)`** — publish/settle/confirm mutex over
  `supervisor/cluster-all/backup/leader`, will = empty retained payload on that topic. Reads the lease
  first: a held-and-unexpired lease owned by another host → follow without publishing; otherwise
  claim, `leaderSettle` (3s), read back, compare. A broker it cannot reach → run unled.
- **`backupProbe.daily()`** now: elects (server hosts only) → runs stages → `writeRunDocument`
  returns the doc → `publishHostStatus` publishes `supervisor/<host>/backup/status` retained → if
  leader, `finishLeadership`.
- **`finishLeadership`** polls `supervisor/+/backup/status` every `leaderPollInterval` (30s) until
  every `backupExpectedServers` (config hosts with an index) reports a terminal state
  (`complete`/`failed`/`timeout`) for this `run_id`, or `backupRunCeiling` (5h) passes — then
  publishes `OFF` to `config.BackupCommandTopic()` and clears `election` + `leader/status`.
- **DEVIATIONS**: the lease is refreshed only at claim time (not re-published mid-run as the plan's
  "refreshes it as it works" describes — a 5h ceiling on a daily job is generous enough that this
  matters little); `leaderStatusTopic` (`supervisor/cluster-all/backup/status`) is only cleared, never
  populated with the estate roll-up during the run; the leader does **not** adopt a hand-started
  run's in-flight topics; `readRetained` uses a fixed sleep window, not a quiet-period detector.
  None of this is exercised against a real broker.

### Item 2 — influxdb3 server-side prune — built, cascade untested

- **`src/max/influxdb3/src/build/resources/backup.sh`**: `backup_pruned` is overridden — the
  wrapper's version is captured as `influxdb3_pruned_local` via
  `eval "influxdb3_pruned_local () $(declare -f backup_pruned | tail -n +2)"`, then the override
  runs it and `influxdb3_pruned_server`. The server prune computes the live chain (newest `full-*`
  plus every name sorted after it), deletes dead `delta-*` newest-first with `--incremental` (so
  the cascade is always a no-op), then dead `full-*`; idempotent, warns-never-fails.
- **`backup_eligible <name>`** = `[ -d "${BACKUP_INTERNAL_ROOT_DIR}/${name#*-}" ]`; `backup_written`
  now only treats a server name as parent / current full if we still hold its tar directory — an
  ineligible newest name makes the run take a full and the prune reaps the orphan on the same run.
- **DEVIATION / caveat from the plan**: the `full-*` delete-cascade behaviour of
  `influxdb3 delete backup` is undocumented; the plan says test it on a scratch store first. The
  newest-first delta deletion means the cascade is never actually relied on, but this has not been
  run against any influxdb3 server. shellcheck-clean; regenerated `src/main/resources/backup.sh`.

### Secondary-stage GFS thinning — built, functionally tested

- **`backup_pruned_gfs`** added to the generated wrapper (`container.py`): keeps the newest
  `BACKUP_KEEP_DAILY` backups of any kind, the newest `_full` per ISO week for `BACKUP_KEEP_WEEKLY`
  weeks, and the newest `_full` per calendar month for `BACKUP_KEEP_MONTHLY` months. Only a `_full`
  is ever a weekly/monthly point; `_delta` backups survive only in the daily window (they can only
  be selected by the daily rule, which is kind-agnostic). Depth knobs are wrapper variables
  (`${BACKUP_KEEP_*:-7/4/12}` after `.env` is sourced), so a module overrides them in its env files
  — the plan's `<MODULE>_BACKUP_KEEP_*` per-module overrides.
- New `backup.sh --prune-gfs <dir>` mode; `backup/secondary.sh` calls it instead of `--prune`.
  `--prune` (dense window) is unchanged and still used post-backup at the primary stage.
- Tested on a 45-directory fixture spanning ~13 months: 45 → 11 (7 daily + weekly/monthly `_full`
  points), shellcheck-clean, all six generated `backup.sh` regenerated.
- **Per-module depth**: `src/mad/plex/.env_all` sets `BACKUP_KEEP_MONTHLY=2`,
  `src/max/influxdb3/.env_all` sets `BACKUP_KEEP_MONTHLY=3` (the plan's per-module table); daily/weekly
  stay at the wrapper defaults. **DEVIATION**: `influxdb3` does **not** override `backup_pruned_gfs`, so its `_delta` chains on the share are
  thinned by the generic rule; a monthly/weekly point is always a `_full` so it stands alone, but
  a `_delta` straddling the daily/weekly boundary whose parent `_full` falls outside the window is
  not specially protected. Acceptable while there are no backups; revisit if influxdb3's share tail
  ever matters.

### Remaining work — superseded

This list is kept for its history only. Several of its items were done during the review that
follows; the current, accurate list is **Next steps** at the end of this file.

### Review fixes — applied

Found by a review of the unstaged patch; `go build`, `go vet -printf.funcs=derivedf,derivedInertf`,
`gofmt`, `go test ./...` and `shellcheck` all clean afterwards.

- **`fab build` could not have passed** — `usedBackupSpace`'s derivation printed a `float64` through
  `%s`, which `go vet`'s printf analyzer catches because `derivedf` is named in `fabfile.py`. Now
  `%.1f`, and the action is `ActionCompute` beside its `failedBackups` sibling rather than
  `ActionSample`.
- **`service/backup_status` is inert for a module that ships no `backup.sh`.** `probe_impl_services.go`
  discarded the `found` half of `moduleSuccess`, so 21 of the estate's 27 service slots read `false`
  against a `Truthy()` rule — every unenrolled service permanently red, and `false` persisted to
  InfluxDB. Not-enrolled is now `derivedInertf`, so the rule is never evaluated and the derivation
  says why, the same shape as the four host-inert cases. The derivation moved onto the `service`
  struct (`backupStatusDerived`) beside `maxMemoryDerived`, and the ghost path sets it too — a zero
  derivation there would have logged `unstated [service/backup_status]` every pulse.
- **The reaper stole the daily lock.** `reap` probed liveness with `TryLock`/`Unlock` on
  `dailyRunning`, so a gate tick landing inside that window made `daily()`'s own `TryLock` fail and
  return — silently skipping the whole day, since `firedOn` had already advanced. The probe is now
  an `atomic.Bool` the run sets around itself, and the mutex is only ever a mutex.
- **`stages_run` counts what was attempted**, not `len(stages)`, so a primary failure on a server
  reports 100 pct rather than 33.
- **The plug is commanded non-retained.** A retained `cmnd/.../POWER` is re-executed by the device on
  every MQTT connect and a retained `OFF` latches; `publishCommand` is the non-retained sibling of
  `publishRetained` and the three plug publishes use it. The device's own `stat/POWER` stays the
  retained state of record, which is what the reaper already reads.
- **`/etc/fstab` and `/dev` are bound into the container.** `mount.sh` and the stage scripts read
  both, and neither carries the host's view in the container — so `mount_ready` could only ever time
  out at 120 s and the tertiary stage failed on every server, while an edge host's secondary stage
  resolved no share destination. Bound rather than rebased through `$SUPERVISOR_MOUNT` because
  `mount(8)` itself consults `/etc/fstab` at the real path, so rebasing the reads would have fixed
  the lookups and left the mount broken.
- **The stage log was written twice.** The driver assigns `<run>/logs/<stage>.log` to the child's
  stdout and stderr, and the wrapper then `tee -a`'d the same path — two fds, two offsets. The `tee`
  is now taken only on a hand run (`BACKUP_RUN_ID_PASSED` unset).
- **`BACKUP_TIMEOUT_HOURS=0` broke stage serialisation.** The detach test fired under the driver
  too, so the wrapper backgrounded itself and exited 0, the driver recorded the stage complete and
  started the next one over the top of it. Detach now also requires `BACKUP_RUN_ID_PASSED` unset.
  `BACKUP_TIMEOUT_HOURS` also moved below the `.env` source, so it follows the same
  `${VAR:-default}`-after-sourcing convention as every other wrapper variable.
- **`--delete` deleted its own `--temp-dir`.** The tertiary mirror's `.rsync` is extraneous in the
  destination, so it was collected mid-run; it is now excluded.
- **Stages are declared per form-factor.** `broker_entities` bound `STAGE` to all three for every
  host, so `supervisor/raspbpi-{jen,jil}/backup/tertiary/status` was declared and can never be
  published. `generate.py` now binds two stages for an `edge` host and three for a `server`.
- Smaller: `config.json`'s `broker.token` was `$DATABASE_TOKEN` (now `$BROKER_TOKEN`, which the new
  compose `environment:` entry was already overriding); `supervisor/cluster-all/backup/status` has its own
  declared payload, since the generic one carries none of `hosts_expected`/`power_bool`; the
  secondary stage reads `success_bool` with `jq` rather than `grep`ing the JSON text, and clears its
  temp dir with `find -delete` so dotfiles go too; the primary stage records a real `started_ts` and
  `duration_s` and derives `kind` from the backup's own suffix instead of a hardcoded `FULL`;
  `backup_snapshot_thin` reads `BACKUP_KEEP_DAILY`/`_WEEKLY`/`_MONTHLY` instead of restating 7/4/12;
  `_declared_topics` hoists its glob list out of the inner loop; `config.SchemaHost` was dead and is
  gone; the implemented `service.backupStatus` no longer carries a `TODO: Provide implementation`.

**Accepted, not fixed:** `verify.sh` reports every backup topic `missing` until each host has
completed a run, which fails `fab schema` at supervisor and skips every module after it. It clears
itself after the first estate-wide run and recurs for any host that misses a day. A third glob
category — declared, shown by `describe.sh`, exempt from verify's missing direction — is the fix if
this becomes tiresome; the undeclared direction would still catch a stray topic.

### Gaps filled after the review

Four things the first cut left open, each decided rather than deferred.

**The secondary stage no longer claims to deduplicate.** `--link-dest="${dst}"` pointed at the
destination itself, which cannot hardlink a new timestamped directory against its predecessor, so it
was a no-op wearing the name of an optimisation. It is gone rather than repaired: every module's
backup is one tar or dump per run, so there are no repeated files across timestamps for a
per-directory `--link-dest=../<previous>` to catch, and the plan's *Copy rules* claim of
`rsync --link-dest` should be read as the additive `rsync -a` it always actually was.

**The run root is thinned at both ends.** `/home/asystem/supervisor/backup/<run_id>` grew a directory
a day forever, because supervisor ships no `backup.sh` and neither `--prune` nor `--prune-gfs` could
reach it, and the secondary stage then copied the whole accumulating set to the share additively.
`backupProbe.pruneRuns` keeps `backupRunsKept` (30) locally at the end of every run, and the
secondary stage gives the share copy the same grandfather-father-son thinning the modules get —
`backup_thin_runs`, the daily/weekly/monthly rule applied to bare timestamp directories, since a run
record carries no `_full`/`_delta` suffix for `backup_pruned_gfs` to key on. It runs for any promoted
module with no `backup.sh` of its own, which today is supervisor and only supervisor. It is a third
near-copy of that rule beside `backup_pruned_gfs` and `backup_snapshot_thin`, and deliberately so:
the three delete differently (`rm -rf` of a suffixed backup, `rm -rf` of a run record,
`btrfs subvolume delete`), and one helper taking a deleter argument is exactly the parameterised
helper both callers would have to mentally re-expand.

**The leader keeps its lease alive while it works.** The lease was refreshed only between stages, so
a single four-hour primary stage let it expire mid-run and a peer's reaper could cut power underneath
it; and the election client was `SetAutoReconnect(false)` while being held for hours, so a dropped
session left `finishLeadership` spinning to its five-hour deadline and publishing `OFF` into a dead
client. Now `dialBroker` takes a `persistent` flag — true for the election alone, with a 30 s
reconnect cap — a goroutine refreshes the lease every `leaderLeaseRefresh` (15 min) for the life of
the stage loop, and `finishLeadership` refreshes on each of its own 30 s polls. The stage-loop
refresher is cancelled explicitly before the roll-up rather than by `defer`, so it can never
re-publish a lease `finishLeadership` has just cleared. The last will is what made auto-reconnect the
answer rather than the reaper's dial-per-operation pattern: only a held session can clear the lease
when a leader dies.

**`file_count` and `size_mb` come from `rsync --stats`, and brought five more fields with them.** They
were a `find -type f | wc -l` and a `du -m -s` over the whole mirror on every tertiary run and over
the share on every secondary run — a full walk of a multi-terabyte tree for two numbers. rsync
already counts everything it touched, so `backup_counted` in the stage wrapper parses its `--stats`
block and accumulates across the several invocations a stage makes. That made four more numbers free,
so the stage payload grew to:

| Field | Meaning |
|---|---|
| `file_count` | regular files transferred this run |
| `size_mb` | transferred file size |
| `files_held` | files the destination tree now holds |
| `files_created` | files new this run |
| `files_deleted` | files removed this run — the one to watch on the `--delete` mirror |
| `size_held_mb` | total size of the destination tree |
| `sent_mb` | bytes actually sent, so a run's real cost is visible beside its logical size |

`backup_stage_document` reads them as globals rather than taking eight positional arguments, which is
also why the heartbeat's terminal stamp no longer passes zeroes it did not know. The primary stage has
no rsync, so it accumulates its own per-module `du`/`find` over the single newest backup directory —
cheap, already computed — and counts each successful module as one `files_created`. The fields are
declared in `metric.Payloads()`, carried on `backupDocument` (which matters, because
`reapLocalStale` round-trips a stage document through the struct and would otherwise drop anything
undeclared), and rolled into `<run>/status.json` by summing the stages, with the tree totals and
`disk_usage_perc` taken from the tertiary stage alone since only it sees the whole mirror.

### The daily gate became an hourly schedule — built

Supersedes *Step 1* above, which is left as the record of what was built first.

- **One interface, two cadences.** `dailyProbe.daily(ctx)` and `reaperProbe.reap(ctx)` collapsed
  into `scheduledProbe.scheduled(ctx, hour, crossed)`, which now lives in `probe.go`. The loop
  still ticks every minute; it now passes the local hour and whether this tick is the first of a new
  hour. `backupProbe.scheduled` reaps unconditionally and starts a run on
  `crossed && hour == backupScheduledHour`. `reap` is an ordinary unexported method again.
- **Deleted outright:** the `-D/--daily-time` flag, `serveOptions.dailyTime`, `cmd.toDailyMinutes`,
  `config.DefaultDailyTime`, `config.Periods.DailyMinutes`, the `periodic [N] min daily` startup
  line, and `dailyGateDay`/`dailyGateSeed`/`dailyGateFires` with their date-string arithmetic.
  Replaced by `backupScheduledHour = 1`, `scheduleSeed`, `scheduleFires` and `scheduleInterval`.
- **Renamed for consistency:** `dailyRunning`/`dailyActive` → `backupRunning`/`backupActive`, and
  `dailyStart` → `runStart`. `probe_daily.go` was briefly `probe_schedule.go` before the file
  reorganisation below folded it into `probe.go`.
- **BEHAVIOUR CHANGE, and it is the point.** The day-granular gate fired late — a host asleep across
  01:00 ran its backup whenever it woke, which contradicted the plan's own "a host down at 01:00 has
  missed that day". The hourly gate offers the woken hour and the backup ignores it.
- **Cost accepted:** retiming the estate's backup is now a rebuild rather than a flag. Judged right
  because the flag had never been used and it separated the one number deciding when the backup runs
  from the code that runs it. A `config.json` override was considered and rejected as a second
  source of truth for the hour.
- The gate-fired line dropped to DEBUG, since fired hourly it would otherwise be 23 no-op INFO lines
  a day per host.

### The reaper holds a session instead of dialling every minute — built

Found by review: `reap` dialled, subscribed, slept `brokerSettle`, unsubscribed and disconnected on
every tick on every server — roughly 5 700 sessions a day estate-wide — to read three retained
values that change a handful of times a day. The module's own engine already had the right shape for
that question, so the reaper now uses it.

- **`probe_mqtt.go` became `probe_lib_broker.go`, gained a watcher, and was streamlined to three entry
  points.** `brokerDial` (dial-act-disconnect), `brokerHold` (persistent, auto-reconnect, last will
  emptying one retained topic) and `brokerWatch` (persistent, subscribed, latest retained payload per
  topic in memory), over shared `brokerOptions` / `brokerConnect` / `brokerSubscribe` /
  `brokerPayloads`. The old `dialBroker(configPath, suffix, willTopic, willPayload, persistent)`
  signature — three arguments that were `"", "", false` at every call site but one — is gone, as is
  `readRetained`'s window parameter, which was `leaderSettle` at both call sites; `leaderSettle`
  became `brokerSettle`, since the watcher settles the same way.
- **The rename came with a split and a log source.** The file was named for the transport while
  everything in it was named `broker*`, and it logged under `probe[backup]` — breaking the
  one-`scribe.Source`-per-logging-file rule that `probe_lib_drives.go` exists to honour. `backupLease`,
  `electBackupLeader` and the two cluster topic constants moved to `probe_impl_backup.go` where
  the backup policy lives, `probe_lib_broker.go` now contains **no** backup, leader or lease reference,
  and it carries its own `SourceProbeBroker` → `probe[broker]`, so `--log-source=probe[broker]`
  reaches the session lines and `probe[backup]` no longer answers for two files. It also fixes the
  file-based test-naming rule: `TestProbeBackup_LeaseExpired` now sits in the same file as the type
  it tests.
- **Naming is one rule: every package-level identifier in `probe_lib_broker.go` is `broker<Thing>`**, and
  methods drop the prefix because the receiver already scopes them. That resolved the verb-first
  entry points sitting beside noun-first helpers, and `brokerClient.readRetained` /
  `brokerWatcher.readRetained` now differ only by receiver — one dials, one reads the live
  subscription. The type behind the watcher is `brokerWatcher` so the constructor can be
  `brokerWatch`. Bare `dial`/`hold`/`watch` were rejected: `watch` is the module's most overloaded
  word (the dashboard command, `watchStart`, `watchOptions`, `watchWakeListener` and fifteen more),
  and the client ID prefix dropped its `backup` segment to `supervisor-<role>-<nanos>` for the same
  reason the file did.
- **Freshness is connection state, not message age.** The retained set arrives once at subscribe and
  then goes quiet for hours, so a message-age staleness test would fault constantly. `retained()`
  reports fresh only when the client is connected *and* a subscribe has been granted and settled
  since the last connect; `reap` treats not-fresh as unknown and resets `reapIdle` rather than
  powering anything off. This subsumes the SUBACK return-code check added earlier in the same review
  — a refused subscribe simply never becomes ready — and it keeps the fail-closed property that
  matters here, since powering off is the one irreversible thing the reaper does.
- **A lost connection calls `forget()`**, clearing the map and the ready flag, so a vernemq recreate
  cannot leave a phantom "tertiary running" behind; paho resubscribes on reconnect and the store
  repopulates it from whatever is actually retained — nothing at all after a release, which flushes
  it, and the true flag after a restart, which no longer does. `attach` is guarded by a `TryLock`, and `retained()` kicks it when
  the client is connected but not ready, so a subscribe refused seven seconds into a broker recreate
  is retried on the next tick rather than disabling the reaper for the life of the process.
- **The watch is created lazily inside `reap`**, which is already gated on `p.serverHost` and only
  reached from the serve schedule loop — so a `watch` on the dev machine never opens one. Its
  lifetime is the process; there is no teardown hook and none is needed, since it carries no will.
- `finishLeadership` still uses `readRetained` on the held election client, which is bounded (30 s
  polls, leader only, during a run) and needs the subscribe/unsubscribe cycle it already has.

### `internal/probe` files grouped by role — built

The package could not be read from `ls`: `probe_drives.go` (a helper) and `probe_host.go` (a probe)
were indistinguishable by name.

- **Three groups, one prefix each.** `probe.go` is the spine; `probe_impl_*` is a registered probe
  (`backup`, `host`, `services`); `probe_lib_*` is everything supporting (`broker`, `drives`,
  `install`, `logs`, `mounts`, `rule`, `sensors`). Test files and their `Test<File>_<Case>` prefixes
  followed — `TestProbeLibMounts_*`, `TestProbeImplHost_*` and so on.
- **`impl` prefixes the minority deliberately.** Prefixing the helpers instead does not group:
  `probe_services.go` sorts after any `probe_read_*`, splitting the probes. With every probe carrying
  `impl_`, no helper can sort inside the block, so the grouping survives any future name. `lib` beat
  `base`/`read`/`util` on two counts — it sorts before `probe_test.go` where `util` does not, and the
  group's only shared property is *not being a probe*, so a word with more meaning would misdescribe
  the transport or the rule evaluator.
- **`probe_schedule.go` folded into `probe.go`** rather than becoming `probe_lib_schedule.go`.
  `probe.go` now holds every contract a probe can implement, mandatory and optional, which is a
  stronger rule than "a contract lives beside its consumer" and gives one place to answer "what can a
  probe be?". It also resolved a rule break inherited from `probe_daily.go`: that file and `probe.go`
  both logged `SourceProbe`, two files sharing one source. Folding made them one file, so no
  `SourceProbeSchedule` was needed. Its test merged into `probe_test.go` as `TestProbe_Schedule*`.
- **Log sources are unchanged** — the source is the file name's last underscore segment, so the role
  infix is invisible: `probe_lib_drives.go` is still `probe[drives]`.
- **A sub-package for the `lib` half was rejected on measurement, not taste.** `probe_lib_rule.go`
  (6 references to the `probe` interface and `probeMap`) and the schedule loop (3 to the `exec*`
  package vars) cannot move without an import cycle, so the split would be partial from the start.
  The rest would force `derivation`, `derivedf`/`derivedInertf` and the three error sentinels to be
  exported — `probe_lib_mounts.go` alone has 12, 5 and 10 references — plus roughly twenty unexported
  types, in a package whose style forbids the doc comments a public API would need. `probe_lib_broker.go`
  is the only file with zero coupling, and one consumer does not earn a package.
- **CLAUDE.md no longer names an individual test.** A test name is not an interface anybody codes
  against, and pinning one in the doc only guarantees it goes stale at the next split or rename; the
  doc now describes what is enforced and lets the file-prefix rule say where it lives. That also
  removed the last real cost of this rename.
- **`probe_lib_broker.go` gained the test it never had** — the payload store keeping the latest value
  per topic and returning a copy rather than an alias, the watcher reporting fresh only when
  connected *and* granted, and `forget()` clearing both payloads and readiness so a dropped session
  cannot leave a phantom "tertiary running" behind. Written against a stub `mqtt.Client`, and the
  race detector caught an unsynchronised counter in that stub on the first run.

### Backup namespace restructured, and module/service disentangled — built

The topic tree relied on reserved words to tell its levels apart, and `module` was being used for two
different things.

- **Every level is now named.** `supervisor/$HOST/backup/stage/$STAGE/status` and
  `supervisor/$HOST/backup/stage/primary/service/$BACKUP_SERVICE/status` replace the flat
  `backup/$STAGE/status` and `backup/$MODULE/status`, which were the same shape and could only be
  told apart by knowing that `primary|secondary|tertiary` were reserved — a service named `primary`
  would have collided silently. A service topic now nests under the stage that produces it, which is
  true by construction: a service backup only ever happens in the primary stage.
- **`supervisor/leader/...` became `supervisor/cluster-all/...`**, and `election` became `leader`.
  The old form put a *role* at the level every sibling uses for a host, so `supervisor/+/backup/#`
  collected the leader topics by accident; `cluster-all` is the pseudo-host that is the whole estate.
  `leader` names the state the retained payload actually holds — who leads — rather than the process
  that produced it. Constants followed: `clusterLeaderTopic` / `clusterStatusTopic`, and
  `publishLeaderStatus` → `publishClusterStatus`.
- **Depth is 8 of vernemq's `topic_max_depth = 10`**, measured on the deepest declared topic
  (`supervisor/raspbpi-jen/backup/stage/primary/service/zigbee2mqtt/status`). Two levels of headroom;
  anything added below `service/` would need that limit checked.
- **`$BACKUP_SERVICE` is a new placeholder, deliberately distinct from `$SERVICE`.** It binds only
  the enrolled services. They cannot share one name even with separate mappings, because `_expanded`
  raises when a mapping fails to bind a placeholder a template names — so every mapping must bind
  every placeholder, and a merged `$SERVICE` would declare a backup topic for every service on every
  host, all reported `missing` by `verify.sh` forever.
- **module vs service.** A *module* is what is in source control and ships the `backup.sh`; a
  *service* is the container running on a host. The enrolled set is still computed from modules
  (a glob over `src/*/*/src/build/resources/backup.sh`), and everything downstream now says service:
  the topic level, the run-directory node, `backupProbe.serviceSuccess`, `backupSnapshot.services`,
  and the loop variables in `backup/primary.sh` and `backup/secondary.sh`.
- **The run directory was then reshaped to match** — see the entry below, which removed the last
  place the old ambiguity survived.

### The run directory mirrors the topic namespace — built

`<run>/primary/` and `<run>/postgres/` were siblings, so two hardcoded lists had to know which names
were stages. The directory is now the topic tree.

- **`<run>/<path>.json` is `supervisor/<host>/backup/<path>`.** A stage is `stage/<stage>/status.json`
  and a service is `stage/primary/service/<service>/status.json`, nested under the stage that
  produces it because that is where a service backup actually happens. `find <run> -name '*.json'`
  enumerates exactly the topics a run published, which nothing could check before.
- **`.json` and `.log` rather than extensionless leaves.** The mirror costs one extension strip
  instead of being byte-exact; readable files and working editors were judged worth that.
- **Two hardcoded lists deleted**: `backupReservedDir` in `probe_impl_backup.go` and the
  `case ... logs|primary|secondary|tertiary) continue` in `backup/secondary.sh`. Under an explicit
  `service/` level a module named `primary` is a directory at a different path, so neither list has
  anything to guard.
- **The service scan became a glob.** `readNewestRun` walked the run root with a directory test and a
  reserved-name lookup; it is now `filepath.Glob(<run>/stage/primary/service/*/status.json)` with the
  service name taken from the parent directory. `stageStatusPath(runPath, stage)` earned its place at
  three call sites — the roll-up read, the tertiary read and the reaper's write.
- **`logs/` and `logs/service/` are gone.** Each node carries `output.log` beside its `status.json`,
  so the stage wrapper's `mkdir -p "${BACKUP_STAGE_DIR}" "$(dirname "${BACKUP_LOG}")"` collapsed to
  one path, and `backup/primary.sh` no longer pre-creates a log directory. `output.log` is named for
  what it is rather than for its node, since restating the directory was only ever needed to keep the
  logs distinguishable inside a shared tree.
- **Verified by construction**: a fixture run built at exactly the paths the scripts compute, mapped
  back through the one rule, yields the six declared backup topics for `mad` and nothing else.

### The two stage generators are module-local, not shared — built

Plan: `write_container_mount()` and `write_container_backup_stages()` were written into the shared
build library at `src/all/_/src/build/python/asystem/container.py`, beside
`write_container_healthchecks()` and `write_container_backup()`, on the reasoning that a generated
shipped script is what that library is for. Done instead: both moved verbatim into this module's own
`src/build/python/supervisor/generate.py`. `container.py` lost 290 lines; `generate.py` went from 94
to 296 and now holds the two functions above its `__main__` block.

- **They failed both tests for the shared library.** The root `CLAUDE.md` scopes `src/all/_` to
  "everything **every** generate script needs", and this module's own style rule is that a helper is
  earned by a second call site. `write_container_backup()` has seven callers, `write_container_volumes()`
  five, `write_container_certificates()` three; these two had one each, and could only ever have one.
- **The `module_name` parameter was a lie, which is the part that made this a defect rather than a
  tidiness question.** The generated stage script hardcodes `supervisor` six times — `BACKUP_RUN_PATH`
  under `<home>/supervisor/backup/`, `BACKUP_ENV` at `<install>/supervisor/latest/.env`, `-u supervisor`
  on the publish, `supervisor/${SUPERVISOR_HOST}/backup/stage/…` as the topic, and two log sentences —
  so the parameter was honoured only by the trailing `print`. A second module passing its own name
  would have got a script that published to supervisor's topics and read supervisor's `.env`, with
  nothing failing at generate time. `mount.sh` is the same shape, hardcoded to `/backup` and the
  estate's switched disk. Both now take no parameters at all and resolve their paths from the
  module's existing `DIR_ROOT`, so there is no interface left to be wrong about.
- **The three stage names, their prose summaries and their teardown sentences moved with them**,
  which is the second half of the point: that block is backup-design documentation, and it was
  sitting in a library whose contract is to know nothing about backups.
- **The retention defaults deliberately did not move.** `BACKUP_TIMEOUT_HOURS_DEFAULT` and the three
  `BACKUP_KEEP_*_DEFAULT` constants stay in `container.py` and reach `generate.py` through the
  `from asystem import *` star import, because the per-module `backup.sh` that
  `write_container_backup()` generates for seven modules reads the same four values. Copying them
  would have recreated exactly the two-copies-of-one-number problem the `driveRatings` move
  (`write_container_volumes` → `probe_lib_drives.go`) was made to close.
- **What stays shared is the pattern, not the code.** Read a fragment from `src/build/resources/`,
  wrap it in the banner, chmod, print — already expressed by `write_container_healthchecks()` and
  `write_container_backup()`. Re-instantiating a five-line pattern locally is cheaper than a
  parameterised wrapper both callers would have to mentally re-expand, which is the module's stated
  rule on helpers.
- **Verified byte-identical**: the six stage scripts and `mount.sh` were snapshotted, `fab generate`
  re-run, and `diff -r` reports no change. `fab generate` is otherwise unaffected — nothing else in
  the repo referenced either name.
- **The one argument the other way, recorded so it is not rediscovered as new.** If a second module
  ever grows a multi-stage run, the reusable half is the wrapper — the heartbeat, `backup_stage_document`,
  `backup_counted`, the timeout/reap contract. That is speculative, the wrapper would need real
  parameterisation rather than a name string to serve it, and the move back is mechanical. Do not
  hold the current shape for it.


### `volumes.sh` no longer coordinates with the backup lock — removed

Built, then removed. `write_container_volumes` in the shared `container.py` grew two guards ahead of
the fstab rewrite — a `flock -n` probe of `/home/asystem/supervisor/backup/.lock` and a
`pgrep -f '/asystem/etc/backup/[a-z]+/start\.sh'` — so that changing volumes during a backup run
failed loudly instead of unmounting a live `rsync`. Both are gone, and the six generated
`volumes.sh` copies were regenerated (70 lines deleted across seven files).

- **Removed on the operator's judgement, not on a technical argument.** Volumes are changed by hand,
  rarely, during a deliberate disk operation; the decision is never to run one while a backup is
  running or about to run. A guard against a thing that will not happen is code that must be
  understood, kept working and reasoned about at every future change to either side.
- **The protection was one-directional anyway, which is what prompted the question.** `volumes.sh`
  only *probed* the lock — `flock -n "$file" true` acquires and releases inside that one command —
  so a backup starting *during* a volumes change was never blocked. Closing that would have meant
  `volumes.sh` holding the lock for its duration, which is the change that was rejected in favour of
  deleting the mechanism.
- **`.lock` is not a volume lock and should not have become one.** Its path is inside supervisor's
  run root and its name says "a backup run is in progress"; `volumes.sh` was reading it as "it is
  unsafe to touch `/share` and `/backup`". Those coincided only because backup is the sole writer.
  Generalising it properly would have meant a volume-scoped path spelled identically in Python-generated
  shell and in Go, with nothing to keep the two literals in step.
- **The `pgrep` went with it.** It existed to cover the one path no lock reaches — a stage script run
  by hand, which takes no lock — so with the flock probe gone it guarded half a case.
- **What replaces both is the operator rule already written above**: do not release a host module
  while a stage is running. It is stated in the propagation section beside the fstab steps, which is
  where somebody about to do this is already reading.


### `volumes.sh` audited, extended to `/backup`, and given a formatter — built

The script was 60 lines that unconditionally rewrote `/etc/fstab` and `umount -f`'d everything under
`/share` and `/backup` on every host-module release. It is now 470 generated lines with three verbs,
`volumes.sh [check|apply|format]`, and the destructive half is unreachable from a release.

- **`check` is read-only and is the new census.** It resolves every declared volume to its device,
  reports present/mounted/declared-fstype per line, and faults on the three things that were
  previously invisible — a declared fstype that disagrees with what `blkid` reports, a volume mounted
  from a device other than the one it declares, and two declarations resolving to the same device.
  For a btrfs `/backup` it also checks `share` and one subvolume per locally owned share exist, since
  `backup_snapshot` skips a plain directory **silently**. `apply` ends by running it.
- **`apply` is idempotent and non-destructive, and reports what it changed.** `/etc/fstab` is written
  only when it differs (and a timestamped `.bak` is kept beside the original pristine one); a volume
  is unmounted only when it is mounted *and no longer declared*, and even then only under `--force`;
  mounts are per declared target rather than a blanket `mount -a`. The old `umount -f` of every
  volume on every release is gone. A run that has nothing to do prints `changed [0]`.
- **The partition label is the idempotency check, exactly as intended.** `format` resolves the
  declared `PARTLABEL`; if it exists and holds btrfs the disk is already prepared, so it converges
  the subvolumes and returns without touching the partition table. If the label exists holding
  *anything else* it refuses outright rather than relabelling or reformatting — the case the rule was
  asked for. Only an absent label reaches the destructive path.
- **The disk must be blank, and that single rule is what makes format safe.** No partition, no
  partition label, no filesystem, no signature `wipefs -n` can see. A disk carrying a label of any
  kind already belongs to something — `share_NN`, another host's `backup_NN`, an EFI or LVM member,
  or a label this estate has never heard of — so the script refuses and prints the `wipefs`/`sgdisk`
  to run by hand. Clearing a disk became a deliberate act with its own command, and `format` now only
  ever writes to a disk that is already empty; it no longer runs `wipefs -a` at all.
- **The earlier guard was an allow/deny list and it had a hole.** It refused `share_*`, LVM, mdraid,
  LUKS, EFI, anything mounted and anything this host's `/etc/fstab` claimed — which let a disk
  carrying **another host's `backup_NN`** through, since that label appears in no fstab on the host
  doing the formatting. The clean-disk rule subsumes every case; the specific checks are kept only
  because they name the hazard in the error rather than reporting a generic "not clean".
- **`--serial` is required, and it is the other half.** A `/dev/sdX` name moves between boots, so
  naming the disk by path alone is how the wrong disk gets destroyed. The guard also refuses a
  partition given where a whole disk was asked for, a disk with anything mounted, swap in use, and
  device-mapper or raid holders. Without `--force` it prints the plan and exits.
- **A release can never format, and the installer cannot either.** The six host modules'
  `install.sh` now names its verb — `volumes.sh apply` — where it used to call the script bare. An
  `install.sh drives` dispatch was built first and then removed: once `apply` is explicit, the
  dispatch was the *only* way the installer could reach the destructive verb, so deleting it makes
  `install.sh` incapable of formatting rather than merely unlikely to. `format` is run by name on the
  host, by a person.
- **The dispatch also walked into the substitution trap before it was deleted**, which is worth
  recording since the next hook in one of these files will meet it too. `src/resources.txt` lists
  `../install.sh`, and `varsubst` turns `${1:-install}` into `$1`, discarding the default — the trap
  the root `CLAUDE.md` records against `wait_service`'s `fatal="${5:-true}"`. `${1-}` passes through
  verbatim; confirmed by running `_substitute_env`'s own resolver over the file.
- **Build-time partlabel check.** `_verify_container_partlabels` reads every host module's fstab at
  `fab generate` and prints a warning for a `PARTLABEL` claimed by more than one host. It warns
  rather than fails, because the estate has such a case today and the fix is physical.
- **Verified against production**: `check` on `mad` and `max`, and every `format` refusal path on
  `mad` — missing `--serial`, wrong `--serial`, a partition given as `--disk`, a mounted share disk,
  and a host with no formatter installed. The label and cleanliness refusals were exercised against
  stubbed `lsblk`/`wipefs` on `mad`, since no spare disk exists to carry a `backup_NN` or a stray
  label: a disk carrying `backup_05`, one carrying `share_08`, one carrying an unknown `data_01`, one
  holding ext4 with no label, and a genuinely blank one, which reaches the plan and then refuses for
  want of `--force`. `apply` is **not** exercised against a live host, since it
  writes `/etc/fstab` and remounts; it runs for real on the next host-module release.
- **Two estate faults this surfaced, neither fixed here** — `backup_04` is declared live by both
  `max` and `meg`, and `sgdisk` is missing on every host but `mad` while `btrfs-progs` is missing on
  `may` and `meg`. Both are recorded under the propagation steps.


## Next steps

Ordered by dependency, not by size. Nothing below has been exercised against a broker, a btrfs disk
or a production host.

### 1 Regenerate, build, schema

Generate is stale again — the `rsync --stats` fields landed after the last run, and
`grep -rl sent_mb src/build/resources/schema/vernemq/model/` returns nothing.

```bash
cd ~/Code/asystem/src/all/supervisor && fab generate
git diff --stat -- src/build/resources/schema/ src/main/resources/image/
```

Expect every `backup/*/status/payload` and `backup/status/payload` leaf to gain `files_held`,
`files_created`, `files_deleted`, `size_held_mb` and `sent_mb`, and
`supervisor/cluster-all/backup/status/payload` to change shape entirely — it has its own declaration now
rather than borrowing the stage one. Nothing else should move.

Then `fab build`, re-reading the three probe files for `modernize` rewrites since they have changed
substantially. `fab schema` will fail verify at supervisor with roughly forty `missing` backup
topics until step 7 has run somewhere — the accepted behaviour recorded above — and because a
non-zero exit aborts the task, **every module after supervisor is skipped**. Use
`FAB_SKIP_HOST_ALLBUT` to reach the others, or accept the gap until the first run.

### 2 Systest

```bash
cd ~/Code/asystem/src/all/supervisor && fab st
```

Supervisor ships no `system_test.py`, so this is a compose up/down plus `install_local.sh` running
the regenerated `image/broker.sh` against the throwaway broker — whose sweep is now three narrow
globs instead of `supervisor/${SUPERVISOR_HOST}/#`. `SUPERVISOR_HOST=host.docker.internal` matches
no schema entry, so `HostIndex` is false and there is no tertiary stage, no election and no plug,
which is correct.

**One new risk.** The compose file now binds `/etc/fstab:/etc/fstab:ro`. If Docker Desktop's Linux
VM has no `/etc/fstab`, docker creates a **directory** at that path and any `awk` against it fails.
Nothing in the systest path reads it, but if the container will not start, check that bind first.

### 3 Release the six enrolled modules and prove their backups

Before any supervisor stage testing. Every enrolled module's `backup.sh` was regenerated — new
`BACKUP_KEEP_*`, `BACKUP_TIMEOUT_HOURS`, `--prune-gfs`, and for influxdb3 the server-side prune and
`backup_eligible` — and none of it is on a host. Do this first: the primary stage is nothing but a
loop over these scripts, and debugging six modules through three stages at once is the harder
problem.

**Rehearse a restore before wiping anything.** `mad`'s 3.8 GB of plex backups and the 2.4 GB
plex-rescue on `/share/10` are the only artefacts production has ever made. Once they are gone,
item 1 can only be tested against backups the new code wrote, which proves the new code against
itself.

```bash
# 3a restore rehearsal, into throwaway targets, writing the runbook as you go
#    postgres:  gunzip -c <ts>_full.sql.gz | docker exec -i <scratch-pg> psql -U postgres
#    mariadb:   gunzip -c <ts>_full.sql.gz | docker exec -i <scratch-mariadb> mariadb -uroot -p
#    file copy: tar xzf <mod>_<ts>_<v>_full.tar.gz -C <scratch dir>, redeploy, confirm start
#    influxdb3: untar _full then each _delta in timestamp order, then influxdb3 restore
```

Then per module — `plex` and `postgres` on `mad`, `influxdb3` on `max`, `letsencrypt` on `may`,
`mariadb` on `meg`, `zigbee2mqtt` on `jen`:

```bash
cd ~/Code/asystem/src/<host>/<mod> && fab release

ssh root@<host> "rm -rf /home/asystem/<mod>/backup/*"
ssh root@<host> "rm -rf /share/<n>/backup/<mod>/*"

# influxdb3 only, whose server holds copies the tar directories point at
ssh root@macmini-max 'docker exec influxdb3 influxdb3 list backups'
ssh root@macmini-max 'docker exec influxdb3 influxdb3 delete backup --name <each> [--incremental]'

ssh root@<host> "BACKUP_SKIP_HOURS=0 /var/lib/asystem/install/<mod>/latest/backup.sh"
ssh root@<host> "ls -la /home/asystem/<mod>/backup/*/"
```

Per module, check the artefact is non-trivially sized and opens (`gunzip -t`, `tar tzf`,
`sqlite3 .schema`); the service came back if the snippet stopped it; `backup_unmatched` reported
nothing it should have covered; and a second run inside `BACKUP_SKIP_HOURS` is a no-op. Run
**influxdb3 twice** — the first takes a `full-*`, the second a `delta-*` parented on it, and
`influxdb3_pruned_server` should leave both alive. Then exercise the thinning against a fixture
rather than waiting a year:

```bash
ssh root@<host> "/var/lib/asystem/install/<mod>/latest/backup.sh --prune-gfs /share/<n>/backup/<mod>"
```

### 4 Five module snippets — item 6

`homeassistant`, `mlflow`, `sonarr`, `sabnzbd`, `grafana`, each still needing its approach confirmed
before a line is written: HA's `/api/services/backup/create`; mlflow's share-mounted artefact root,
where the first question is whether it holds anything irreproducible at all; Sonarr's v3 `Backup`
command against the plex stop-and-tar pattern; sabnzbd's `sabnzbd.ini` plus `admin/`, which is
written live and must be quiesced; and grafana's `sqlite3 .backup`, the one that is online-safe.

Two things changed. These five no longer redden their service boxes, so this is a real gap rather
than a dashboard emergency. And adding `src/build/resources/backup.sh` to a module now
**auto-declares** its `supervisor/$HOST/backup/stage/primary/service/$BACKUP_SERVICE/status` topic, because `generate.py` derives
the enrolled set from that glob — so each snippet needs a `fab generate` in **supervisor**
afterwards, not only in its own module.

### 5 Host provisioning — item 14

```bash
# 5a propagation, each host
for h in mad max meg; do ssh root@macmini-$h 'findmnt -o TARGET,PROPAGATION / /share | head -3'; done
ssh root@raspbpi-jen 'findmnt -o TARGET,PROPAGATION /'
```

A `private` on `/` or `/share` needs a systemd oneshot running `mount --make-rshared /` ordered
`Before=docker.service`. `may` is already `shared`; expect the rest to be too.

**5b `/backup` fstab entry — edit the repo, never the host.** Each host's fstab is a **committed
artifact** at `src/<host>/_<os>_<host>/src/main/resources/fstab`, and that host module's
`volumes.sh` copies it over `/etc/fstab` on every release (backing up to `/etc/fstab.bak` once),
creates every `/share` and `/backup` mountpoint `750 graham:users`, runs `mount -a` then
`mount -a -O noauto`, and finally unmounts every `noauto` entry again. So a hand-edit of
`/etc/fstab` survives only until the next `_debian_*`/`_fedora_*` release, and the `noauto` `/backup`
entry is already validated by the release itself — it is mounted once to prove it works and left
unmounted for `mount.sh`.

**The entries already exist.** Three of the four servers carry a `/backup` line today, two of them
commented out:

| Host | Line in the repo fstab | State |
|---|---|---|
| `mad` | `#PARTLABEL=backup_06  /backup  ext4  noatime,errors=remount-ro,noauto  0 2` | commented |
| `max` | `PARTLABEL=backup_04  /backup  ext4  noatime,errors=remount-ro,noauto  0 2` | live |
| `may` | `#PARTLABEL=backup_05  /backup  ext4  noatime,errors=remount-ro,noauto  0 2` | commented |
| `meg` | `PARTLABEL=backup_04  /backup  ext4  noatime,errors=remount-ro,noauto  0 2` | live |
| `jen` | `#PARTLABEL=backup_01  /backup/90  ext4  noatime,errors=remount-ro,noauto  0 2` | commented, and **leave it so** |

`jen` is an `edge` host: it has no share index, so `HostIndex` is false, it runs no tertiary stage
and never invokes `mount.sh`. Note its mountpoint is `/backup/90` rather than `/backup`, which
`mount_targets` would match on its `^/backup/` arm if anything ever did call it there.

**Two estate faults, found by the `volumes.sh` audit and not fixed by it.**

- **`backup_04` is declared live by both `max` and `meg`.** Every other label in the estate is
  unique, and the uniqueness convention is what the `grep -h PARTLABEL` step below exists to keep.
  Two hosts claiming one label is harmless while each disk stays on its own host, and is a data-loss
  hazard the moment one is moved or rewired — the receiving host would mount the other's backup disk
  at `/backup` and tertiary would `rsync -a --delete` its own shares over it. Relabelling is a
  physical act on one disk, so the build only warns; pick a free label for one of them and `sgdisk -c`
  it. `fab generate` in any host module prints the warning.
- **The formatter is not installed where it is needed.** `sgdisk` is present only on `mad`;
  `mkfs.btrfs`/`btrfs` are missing on `may` and `meg`. `volumes.sh format` refuses with the package
  names rather than half-preparing a disk, so install `gdisk` and `btrfs-progs` on the host first.

**The identifier is a `PARTLABEL`, not a UUID** — the GPT partition name, which is what the whole
estate uses for every attached share and backup disk, because it survives a reformat and names the
disk's role rather than its contents. So for a host whose line is commented, the work is: attach the
disk, give its partition the `PARTLABEL` the line already names, uncomment the line, release the
host module.

```bash
# on the host, find the disk and confirm it is the right one
lsblk -o NAME,SIZE,TYPE,PARTLABEL,MOUNTPOINT,MODEL,SERIAL
```

```bash
# one variable at a time - set these three by hand from the output above
DISK=/dev/sda                 # the whole disk, not a partition
PART=/dev/sda1                # the partition that will hold /backup
LABEL=backup_06               # the PARTLABEL the repo fstab already names for this host
```

```bash
# every PARTLABEL the estate has already used, so a new one does not collide
grep -h PARTLABEL ~/Code/asystem/src/*/_*/src/main/resources/fstab | awk '{print $1}' | sort -u
```

```bash
# read the partition's current PARTLABEL, and set it if it is wrong or absent
blkid -s PARTLABEL -o value "${PART}"
sgdisk -c 1:"${LABEL}" "${DISK}"          # GPT partition name; 1 is the partition number
partprobe "${DISK}"
blkid -s PARTLABEL -o value "${PART}"     # confirm it took
```

Then uncomment the `/backup` line in `src/<host>/_<os>_<host>/src/main/resources/fstab` and:

```bash
cd ~/Code/asystem/src/<host>/_<os>_<host> && fab release
ssh root@macmini-<host> 'grep backup /etc/fstab && ls -ld /backup && mountpoint /backup'
#   expect: the line present, /backup existing 750 graham:users, and NOT mounted
```

**`volumes.sh` unmounts everything under `/share` and `/backup` before it re-mounts**, so releasing a
host module during a backup run will pull the filesystem out from under a live `rsync`. Do not
release one while a stage is running.

**5c `jen`'s share.** Already present and correct — `//macmini-mad/share-10 /share/10 cifs …
x-systemd.automount`. Nothing to add; `jen` has no `/backup`.

**5d Prove the container boundary** on one server and on `jen`, after supervisor has been released
with the new compose — the four binds and the capability are only in the repo until then.

```bash
ssh root@macmini-mad 'docker exec supervisor cat /etc/fstab | head'
ssh root@macmini-mad 'docker exec supervisor ls /dev/disk/by-partlabel'
ssh root@macmini-mad 'docker exec supervisor mount -t tmpfs none /mnt/x && echo APPARMOR_OK'
ssh root@raspbpi-jen 'docker exec supervisor ls /share/10 && echo EDGE_SHARE_OK'
```

The first must print fstab lines rather than nothing — a directory there means docker created the
bind source because the host had no `/etc/fstab`. The second is what `mount.sh`'s readiness wait
actually resolves, since the fstab identifier is a `PARTLABEL`.

**5e Optional: convert `/backup` to btrfs.** `backup_snapshot` and `backup_btrfs_usage` guard on
`btrfs subvolume show` and stay inert until this is done, so it can be deferred — the mirror works on
ext4, it just keeps no history. **This destroys the disk.** Do one host at a time.

**The hand sequence below is now `volumes.sh format`, and that is the only supported way to run it.**
The steps are kept for reference, but the script performs them behind a guard no hand sequence has —
it refuses unless the declared `PARTLABEL` resolves nowhere, the repo fstab declares that volume
`btrfs`, `--disk` names a whole disk, `--serial` matches that disk's own serial, nothing on it is
mounted or in use as swap or held by device-mapper, it carries no `share_*`, LVM, mdraid, LUKS or EFI
partition, no `/etc/fstab` entry resolves to it, and `--force` is given. Without `--force` it prints
the plan and changes nothing. Run it by name on the host; the installer only ever
runs `apply`, so no release path reaches it:

```bash
ssh root@macmini-<host> '/var/lib/asystem/install/_<os>_<host>/latest/volumes.sh format \
  --disk=/dev/sdX --serial=<the disk serial from lsblk> --force'
```

Change that host's fstab line to `btrfs` **first** — format refuses while the declaration says
`ext4`, since formatting to something the fstab cannot mount is the one outcome no guard could
undo.

```bash
DISK=/dev/sda
PART=/dev/sda1
LABEL=backup_06
```

```bash
# 1 - make sure nothing is on it and nothing is using it
lsblk -o NAME,SIZE,TYPE,PARTLABEL,MOUNTPOINT,MODEL,SERIAL "${DISK}"
umount /backup 2>/dev/null
mountpoint /backup                        # must say "is not a mountpoint"
```

```bash
# 2 - repartition, one GPT partition spanning the disk, named with the PARTLABEL
wipefs -a "${DISK}"
sgdisk -Z "${DISK}"
sgdisk -n 1:0:0 -t 1:8300 -c 1:"${LABEL}" "${DISK}"
partprobe "${DISK}"
blkid -s PARTLABEL -o value "${PART}"     # must print ${LABEL}
```

```bash
# 3 - btrfs, filesystem label matching the partition label
mkfs.btrfs -L "${LABEL}" --csum xxhash -m dup -f "${PART}"
mount -o noatime,compress=zstd:3 "${PART}" /backup
btrfs subvolume create /backup/share
```

```bash
# 4 - which shares this host owns, ie the local ones, not a peer's over cifs
findmnt -rn -o TARGET,SOURCE,FSTYPE | grep -E '^/share/[0-9]+ '
```

```bash
# 5 - one subvolume per owned share, one line at a time from the output above
#     mad owns /share/10 /share/11 /share/12, max /share/20 /share/21,
#     may /share/30 /share/31 /share/32, meg /share/40 /share/41 /share/42
btrfs subvolume create /backup/share/10
btrfs subvolume create /backup/share/11
btrfs subvolume create /backup/share/12
btrfs subvolume list /backup              # share, plus one per owned share
umount /backup
```

Then change that host's line in `src/<host>/_<os>_<host>/src/main/resources/fstab` from `ext4` to
`btrfs`, keeping the `PARTLABEL` and `noauto`, and release the host module:

```
PARTLABEL=backup_06  /backup  btrfs  noatime,compress=zstd:3,noauto  0 2
```

```bash
cd ~/Code/asystem/src/<host>/_<os>_<host> && fab release
ssh root@macmini-<host> 'mount /backup && findmnt /backup && btrfs subvolume list /backup && umount /backup'
```

Notes on the choices. `errors=remount-ro` is an ext4 option and is dropped — btrfs does not merely
ignore it, **`mount` fails outright**, verified on `mad` against a loopback btrfs, so a `/backup` line
carrying it never mounts at all. The pass field goes to `0` with it: btrfs has no fsck pass. `compress=zstd:3` is a **mount** option, so it belongs in fstab rather than
in `mkfs`; the estate's root filesystem on `mad` already uses `compress=zstd:1`, and `3` is chosen
here because a backup mirror is written once and read rarely. `autodefrag` is deliberately **off**,
since the workload is large sequential rsync writes rather than random small ones. Each
`/backup/share/<n>` **must** be its own subvolume or `backup_snapshot` skips it silently — a plain
directory is not snapshottable. Only the host's **own** shares get a subvolume, the same rule
`backup_local_shares` applies at runtime, so a peer's cifs share is never mirrored.
`/backup/.snapshots` needs no preparation: `backup_snapshot` creates it, and the snapshots inside are
read-only and thinned by `backup_snapshot_thin`.

**Two mkfs choices matter more on a multi-TB spinning disk than any mount option, and `volumes.sh
format` now passes both.** `--csum xxhash` replaces the crc32c default, which is the bottleneck when
scrubbing terabytes; `-m dup` states the single-device metadata default explicitly, so two copies of
the metadata survive a bad sector and a future btrfs-progs default cannot silently drop it on the one
filesystem where it matters most. Both verified accepted on `mad` (btrfs-progs 6.16.1). `nossd` is
worth adding to the mount options for the same reason `probe_lib_drives.go` refuses to trust
`queue/rotational`: the flag lies in both directions on USB-attached disks, and btrfs picks its
allocator from it.

### 6 influxdb3 `full-*` delete cascade, on a scratch store

Before the new prune runs anywhere real. Record the outcome under *2 influxdb3 keeps two copies and
prunes neither*.

```bash
docker exec influxdb3 influxdb3 create backup --name full-test
docker exec influxdb3 influxdb3 create backup --name delta-test --incremental --parent full-test
docker exec influxdb3 influxdb3 delete backup --name full-test
docker exec influxdb3 influxdb3 status backup --name delta-test
```

All three possible answers — cascaded, refused, silently orphaned — are safe given the newest-first
deletion order the snippet uses. The point is knowing which one it is.

### 7 First real supervisor multi-stage run

Release supervisor, then run each stage by hand uncapped, because a first full sync of terabytes
will blow the deployed three-hour cap. `BACKUP_TIMEOUT_HOURS=0` is for hand runs only: the script
detaches and disowns, the heartbeat keeps `expires_ts` fresh while it lives, and the reaper still
runs `stop.sh` if the process dies and still powers `/backup` off after a clean completion.

```bash
RUNID=$(date +%Y-%m-%d_%H-%M-%S)
INSTALL=/var/lib/asystem/install/supervisor/latest/image

ssh root@macmini-mad "BACKUP_TIMEOUT_HOURS=0 ${INSTALL}/backup.sh primary start $RUNID"
ssh root@macmini-mad "tail -f /home/asystem/supervisor/backup/$RUNID/logs/primary.log"

ssh root@macmini-mad "BACKUP_TIMEOUT_HOURS=0 ${INSTALL}/backup.sh secondary start $RUNID"
ssh root@macmini-mad "ls /share/10/backup/"

# tertiary needs 5d proven and the plug on; supervisor only publishes ON at the head of daily(),
# so a hand run outside the daily window powers it up itself - and note no -r, the command is
# published non-retained now
set -a; . /var/lib/asystem/install/supervisor/latest/.env; set +a
mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u supervisor -P "$BROKER_TOKEN"} \
  -q 1 -t tasmota/device/rack_backup_plug/cmnd/POWER -m ON
ssh root@macmini-mad "BACKUP_TIMEOUT_HOURS=0 ${INSTALL}/backup.sh tertiary start $RUNID"
```

Then check each stage's `status.json` carries the seven count fields with plausible values — the
first proof that `backup_counted` parses the installed rsync's `--stats` block, which has so far
only been tested against synthetic output. Hand over to the daily gate at the deployed three-hour
cap, watch one scheduled run end to end, and confirm the retained backup topics survive an
`install.sh schema broker`, which they must because `broker_topic_glob_data` excludes them by
design.

```bash
mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u supervisor -P "$BROKER_TOKEN"} -v \
  -t tasmota/device/rack_backup_plug/stat/POWER \
  -t 'supervisor/+/backup/#' -t 'supervisor/cluster-all/backup/#'
```

After a clean tertiary run expect the plug `stat` OFF, tertiary status `complete`, the election
cleared and `leader/status` terminal then cleared.

### Provisioning corrections found while writing the next steps

Reading the estate's committed fstab files turned up three things the plan had wrong.

**The fstab is a repo artifact, not a host file.** Each host has one at
`src/<host>/_<os>_<host>/src/main/resources/fstab`, and that host module's generated `volumes.sh`
copies it over `/etc/fstab` on every release, creates the mountpoints, mounts everything, then
unmounts every `noauto` entry again. A hand-edit on a host survives until the next
`_debian_*`/`_fedora_*` release. The `/backup` lines **already exist** — live on `max` and `meg`,
commented on `mad`, `may` and `jen` — so provisioning a server is uncommenting a line and releasing
the host module, not authoring one.

**The identifier is a `PARTLABEL`, and `mount.sh` could not read one.** `mount_ready` handled
`UUID=`, `LABEL=` and `/dev/*` and fell through `*)` for anything else — and `PARTLABEL=` does not
match `LABEL=*`, so it took the silent no-op arm. Since **every** attached share and backup disk in
the estate is declared by `PARTLABEL`, the readiness wait was inert everywhere it mattered: `up`
would go straight to `mount` without waiting for the disk to spin up and enumerate, which is the one
thing it exists to do. `PARTLABEL=` and `PARTUUID=` now resolve through `/dev/disk/by-partlabel` and
`/dev/disk/by-partuuid`.

**`volumes.sh` would have unmounted a running backup.** It `umount -f`s everything under `/share` and
`/backup` before re-mounting, which mid-tertiary would pull the filesystem out from under a live
`rsync`. It briefly refused to run when the supervisor run lock was held or a stage script was
executing; **both guards were removed** — see the deviation below — leaving this an operator rule
rather than an enforced one. It was hardened while there, and that half stands: mountpoints are
matched on the whole field rather than by substring
(so a `/backupfoo` can never be caught), comment lines are skipped consistently, unmount is
`umount` then `-l` then `-f` with a per-mountpoint verification rather than a `find -mindepth 2`
proxy, and each `noauto` entry is mounted, reported with `duf` and unmounted again as a live check of
the declaration. Neither an unmounted automount entry nor a `noauto` volume that will not mount is a
failure — the first is what `x-systemd.automount` and `nofail` mean, and the second is the normal
state of `/backup`, whose disk is powered down between runs. The only new failure is a volume left
mounted after that check.

### The daily gate is serve's alone, expressed by absence

`probe.Run` took a `runDaily bool` that `RunListeningProbesLoop` and `RunAllProbesOnce` passed
`false` and only the serve loop passed `true`, and `watch` carried a `dailyTime` field with no flag
behind it, assigned `config.DefaultDailyTime` at the top of `executeWatch` purely to satisfy
`makePeriods`. Nothing was broken — a `watch` never fired a backup — but the shape said the opposite
of the intent: every caller had to state that it did not want scheduled work, and the one flag a
`watch` must never have was being given a value.

Now the scheduler is its own exported entry point, `probe.RunScheduled(ctx)`, which
`RunAllProbesPublishLoop` starts as a goroutine and the other two loops simply do not call —
**absence is the statement**, and neither can pass the wrong argument because there is no argument.
`probe.Run` is back to `(ctx, onPulse)`, `makePeriods` back to its six periods, and `cmd_watch.go`
has no `dailyTime` field at all. `serve` resolves its own flag into `periods.DailyMinutes` after
`makePeriods` returns, which is also where the `HH:MM` parse error surfaces. The optional-interface
pattern is unchanged and is the right one — `RunScheduled` type-asserts `dailyProbe` and
`reaperProbe` over `execProbes`, the same shape `installReader` uses, so a future daily task is one
more implementer of `daily(ctx)` rather than a second scheduler.

### Removing the stage generators

`write_container_backup_stages()` and `write_container_mount()` are gone from
`src/build/python/supervisor/generate.py`, and `src/build/resources/backup/` and
`src/build/resources/mount.sh` with them. They inlined one ~180-line wrapper into six near-identical
stage scripts — **300 lines of fragment became 1723 lines of output**, held consistent by nothing but
the generator, and a fragment could not be `shellcheck`ed at all because the wrapper defining
`backup_publish`, `backup_count` and the `BACKUP_*` variables was absent from it. Sourcing does
that job structurally and for free.

What ships now, all hand-authored under `src/main/resources/image/` and each passing `shellcheck -x`:

```
backup.sh                the runner: backup.sh <stage> [start|stop] [run-id]
backup/lib.sh            the shared functions, sourced before the stage; the stage contract is its header
backup/primary.sh        stage_start and stage_stop, nothing else
backup/secondary.sh
backup/tertiary.sh
mount.sh                 unchanged, and it never had a parameter to interpolate in the first place
```

**start and stop became one file per stage**, since `stop` is two lines everywhere and the phase was
already a variable inside the wrapper. Go execs `bash /asystem/etc/backup.sh <stage> <phase> <run-id>`
from three sites in `probe_impl_backup.go`; `backupStageDir` became `backupRunner` and
`backupProbe.stageDir` became `backupProbe.runner`.

**The four numbers the generator interpolated travel in `config.json` instead**, which the stages
already open with `jq` for the host's service list and share index. `container.py` stays the single
owner of `BACKUP_TIMEOUT_HOURS_DEFAULT` and the three `BACKUP_KEEP_*_DEFAULT`; `generate.py` writes
them into `asystem.backup` beside the plug topics; `backup_config` reads them behind an env
override. No new file, no new env var, and nothing that would put a `${VAR:-default}` into a file
`src/resources.txt` substitutes.

**`backup_thin_runs` and `backup_snapshot_thin` collapsed into `backup_thin <dir>`.** The two were
byte-identical apart from the delete, and the reason they were kept apart — one generated file each —
stopped existing the moment both landed in `lib.sh`. It takes no deleter argument: `btrfs subvolume
delete` falling back to `rm -rf` decides per entry, the same internal switching `backup_usage` uses,
so secondary's bare run records and tertiary's read-only snapshots both go through one call.
`backup_pruned_gfs` in `container.py` stays separate: different file, different lifecycle, and it
thins files by suffix rather than directories by timestamp.

Two other tidies fell out of hand-authoring: `backup_guard_mounted` was dead in all six generated
copies and is gone, and `backup_disk_usage` and `backup_btrfs_usage` became one `backup_usage
<mount>` that assigns `BACKUP_USAGE` itself rather than being command-substituted into it. It
switches internally rather than taking a flag: `btrfs filesystem show` already answers "is this
btrfs" as a side effect of trying, so a caller never has to know which its mount is, and a
non-btrfs mount, an unreadable allocation tree or an absent `btrfs` binary all fall through to
`df`. Because it lives in `lib.sh`, no stage file assigns `BACKUP_USAGE` and none needs a
`shellcheck disable=SC2034`. One consequence worth knowing: primary and secondary now report the
btrfs figure on a btrfs host where they used to report `df`. That is the better number — `df`
against btrfs answers a different question — and it reaches no metric, since
`host/used_backup_space` reads the **tertiary** stage's `disk_usage_perc` alone, which was
btrfs-preferred already.

Verified: `shellcheck -x` clean on all six scripts, `go build`/`vet`/`test ./...` pass, `fab generate`
runs and leaves the scripts alone, and the runner was exercised end to end in a `debian:12-slim`
container with a stub stage — usage/exit-2 paths, the status document, the stop phase, the thinner,
and `config.json` driving the retention values (edited to 99/42 to prove it is read rather than
falling back).

**Naming, finally.** Every `lib.sh` function is two words, `backup_<one word>` — imperative where it
acts, a noun where it sets the like-named variable:

| was | is |
|---|---|
| `backup_configured` | `backup_config` |
| `backup_ensure_mounted` | `backup_mount` |
| `backup_counted` | `backup_count` |
| `backup_stage_document` | `backup_document` |
| `backup_thinned` + two deleters | `backup_thin` |
| `backup_disk_usage` + `backup_btrfs_usage` | `backup_usage` |

`backup_publish` and `backup_heartbeat` were already there. In `backup/tertiary.sh`,
`backup_local_shares` and `backup_snapshot` were **inlined into `stage_start`** — one call site each,
which is the module's own rule for when a helper is earned — leaving `backup_ready` (renamed from
`backup_disk_ready`) as the one stage-local function, on the two call sites that justify it. The
inlined enumeration was re-verified against a stubbed `findmnt`: `/dev`-backed `/share/<n>` of a
local fstype only, so a peer's cifs share is still never mirrored.
