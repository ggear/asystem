# Backup and restore, after the 2026-10-22 influxdb3 loss

## What happened

| Time (Perth) | Event |
|---|---|
| 22 Oct 01:00 | Last good nightly delta, `delta-2026-10-22_01-00-08`, on top of `full-2026-10-19_01-00-28` |
| 22 Oct 07:45 | Power cut. `/home` is ext4 with `commit=600`, so PachaTree's newest checkpoints, gen0 manifests and WAL segments come back zero length |
| 07:56–08:15 | Releases 1848–1851 teach `entrypoint.sh` to delete the empty files. Every retained compactor checkpoint was empty, so the compactor restarts at sequence 0 and indexes nothing compacted before it. serve comes up healthy on an empty history |
| 08:11, 08:15 | Pre-install backups faithfully capture the broken state (41K, 53K) |
| 26 Oct 01:00 | The weekly full, `full-2026-10-26` at 10.9M against 177M a week earlier, becomes the newest full. Server-side pruning drops every older chain from the live store |
| 27 Oct | Found from a Grafana gap. Nothing alerted |

Lost for good: 22 Oct 01:00–08:09, which only ever lived in WAL/gen0. Recoverable: 2026-08-13 → 22 Oct 01:00.

### Faults, in the order they compounded

1. **Durability.** `commit=600` on `/`, `/home`, `/var` and `/tmp` on `max`/`may`/`meg`/`jil` (the `_debian_*`/`_fedora_*` `fstab`
   sources) gives up to ten minutes of exposure for anything that is not fsync'd. PachaTree evidently writes its
   checkpoints without fsync before rename. `storage/plans/filesystem.md` already says to drop it. There is no UPS.
2. **Repair turned corruption into silent loss.** Deleting *every* empty checkpoint is safe when one is empty, and a
   reset when all are. It needs to refuse instead.
3. **Nothing noticed the history shrink.** A full 6% the size of its predecessor was accepted, kept and treated as the
   chain root.
4. **Primary pruning ignores chains.** `backup_pruned` deletes by age alone (`BACKUP_RETAIN_DAYS=7`), so on 26 Oct primary
   held deltas from 21 and 22 Oct with their 19 Oct full deleted: unrestorable on their own. The secondary GFS pruner does
   walk chains, which is the only reason the chain survived (`/share/30/backup/influxdb3/`).
5. **GFS would have finished the job.** With `INFLUXDB3_BACKUP_KEEP_MONTHLY=3` and weekly 4, October's monthly point is the
   newest October full, the 26 Oct one. `full-2026-10-19` survives only as a weekly and ages out around 23 Nov.
6. **Restore can only replace.** `restore.sh` applies one artifact into the live service. A delta chain has to be walked by
   hand, and a replace would discard the five days written since.

## Design

The fixes split into one framework change in `container.py`, which owns the wrapper, the GFS window and both contracts,
and a small set of new snippet hooks that each module opts into. Everything below is generic. Module specifics
are limited to the hook bodies.

### 1. Every run writes a manifest

In `<run>/.meta/manifest.json` (never beside the archive, see below), written by the wrapper from a new optional hook:

```
backup_fingerprinted   print one "<unit> <count>" line per unit of the backed-up state
```

| Module | Unit | Count |
|---|---|---|
| influxdb3 | `<table>/<day>` | rows of each closed day, counted on live at backup time (`date_trunc('day', time)`, `count(*)` per table). Its own hook, because a delta's bytes say nothing about the state it restores. No restore runs nightly |
| postgres | `<database>.<table>` | rows, from `COPY` lines counted in the dump stream. Wrapper default for a SQL dump |
| mariadb | `<database>` | bytes, split on the dump's `-- Current Database:` markers. Wrapper default for a SQL dump: no nightly staging |
| plex, letsencrypt, wrangle, homeassistant | each **include** | bytes summed per include from the archive's own listing (`tar -tvzf`). Wrapper default for a `backup_files` module. Never per file: wrangle's bank files carry versions in their names (`_sheet_bank_balances_v18.csv` → `v19`), so 6–21 entries vanish every night |
| zigbee2mqtt | each archive entry | bytes from `unzip -l`. Wrapper default for an API-written archive, whose 8 entries were stable all week |

Only influxdb3 defines `backup_fingerprinted`. Every other module gets the wrapper's default for its artifact type, so
it needs no fingerprint code.

Fingerprints come from the artifact, or from live only for closed units, which nothing writes to any more and so
cannot race the backup. No module restores anything to fingerprint a backup: restores happen only in drills and
real restores. See *Fit across modules* for closed units and expiry.

The manifest also records `kind` (full/delta), `parent` (the full a delta hangs off), `source_version` and `fingerprint`.
`parent` replaces the current inference from directory order, and every later step reads it.

**Sidecars live in `<run>/.meta/`, never beside the archive.** Today three readers take the first file in the run dir,
alphabetically, as the artifact: `restore_resolved` and `backup_versioned` in `container.py`, and supervisor's
`parseBackupArtefact`. `restore_intact` passes any file it does not recognise. A `manifest.json` beside the archive
sorts before mariadb, plex, postgres, wrangle and zigbee2mqtt archives, and a `drill.json` before every module's. Each
would become "the artifact". So `manifest.json` and the drill verdicts go in `<run>/.meta/`, which a bash `*` glob and a
`!entry.IsDir()` filter both skip. Each stage writes its drill verdict only under its own subdir, `.meta/primary/` or
`.meta/secondary/` (§5a). Separately, all three readers select the artifact by its name pattern,
`<module>_at_<run>_from_<version>_{full,delta}.*`, rather than by position. That fix ships before the first manifest is
written.

### 2. Regression guard: a shrinking backup is not a good backup

After writing, the wrapper compares the new fingerprint with the newest *accepted* run's:

- Any closed, durable unit present before and missing now, or a drop in the **module's total** across those units
  beyond `<MODULE>_BACKUP_SHRINK_PERCENT` (default 20, `0` disables), marks the run **regressed**. The threshold is never
  applied per unit, because small units swing proportionally (wrangle's 1.6K `history_adhoc.json` moved 6% in a night). The module declares which
  units are durable, and other units are reported but never guarded. Its archive is kept, since it is still the current state, but:
  - the run is published with a new backup state, `regressed`, through supervisor. That is a vocabulary change:
    `internal/metric/metric_schema.go` owns it, and the shell side mirrors `BACKUP_STATE_REGRESSED` under the existing
    parity test;
  - **it turns the existing indicators red.** The service's `BKP` (`MetricServiceBackupStatus`) reads false, and its
    stage counts as failed in the host's `Fail BKP` (`MetricHostFailedBackupStages`), whose `Bounded(Self, Exactly, 0)`
    rule already turns the host pulse red. Today both only see a process that failed or timed out. From 22 to 27 Oct,
    `Fail BKP` read 0% on all five hosts and influxdb3's `BKP` read true every day, because every backup of the empty
    database succeeded. Their descriptions widen to match: "backup completed and accepted", and "backup stages failing,
    timing out, regressed or failing their drill";
  - **it shows in `backup tail` and `backup list`, with its reason.** Today supervisor sets a service's state from the
    script's exit code alone (`backupOutcome(ok, …)` in `probe_util_backup_stage_primary.go`), and a module script's
    own output goes to `stage/primary/service/<svc>/output.log`, which tail never reads. A regressed run exits 0,
    because its archive is kept, so it would show as `as [success]`. Instead, when the script wrote a new run (the
    newest run differs from the one before the script started), primary reads that run's `.meta/manifest.json` after
    the script exits. A skipped or failed run writes no new run, so it carries no verdict and never re-reads an older
    run's; a run since `--accept`ed reads as accepted. A `regressed` verdict sets the service state to `regressed`.
    That is its own field beside `SuccessBool`, which stays true because the archive was written and kept: secondary's
    `gradedServices` promotes on `SuccessBool`, so a regressed run is still copied to the share and tertiary, and the
    module's GFS pass still runs. The `regressed` field counts as a failure when the stage resolves, so the summary
    row's primary cell and the run's result both read failure. supervisor also writes the verdict's evidence into `run.log`, one line
    per guarded unit that went missing or shrank, plus the module total against the threshold. Followed live, tail
    then reads like this:
    ```
    service/influxdb3  stop  exported [0.0] GiB ... from [influxdb3] as [regressed], kind [delta], version [10.200.1849]
    service/influxdb3  stop  regressed [<n>] closed units missing against [2026-10-22_01-00-08], total [-100]% beyond [20]%, first [sensor__temperature/2026-08-13]
    ```
  - the last accepted full and its chain become the **anchor**, pinned by every pruner (primary, server-side store,
    secondary GFS, retire_home) until acknowledged;
  - acknowledging is `backup.sh --accept=<run>`, which marks the regressed run accepted and releases the anchor. It is
    for an intentional shrink, such as a retention change or a dropped table.
- For influxdb3, the 08:11 pre-install backup on 22 Oct, taken as release 1850 installed over 1849, would have
  flagged: every closed day counted zero on live (§1). The anchor would then have kept `full-2026-10-19` and its
  chain indefinitely, and the install of release 1850 would have been abandoned (invariants). Releases 1848 and 1849
  took no pre-install backup at all (08:11 and 08:15 are the only two), so the guard had nothing to judge for them.
  The invariant that refuses an install without a pre-install backup is what would have stopped 1848.

### 3. One chain-aware pruner, three policies

Replace `backup_pruned` and `backup_pruned_gfs` with one selection function. It takes a keep policy and returns the keep set:

```
keep = policy(runs)  ∪  newest  ∪  anchor-chain  ∪  closure(parents of every kept delta, via manifest.parent)
```

- **primary**: policy = inside `BACKUP_RETAIN_DAYS`. The closure fixes fault 4 directly.
- **secondary GFS**: policy = the existing daily/weekly/monthly tiers. The closure is already there; the anchor is new.
- **influxdb3 server store** (`influxdb3_pruned_server`): becomes a third caller instead of its own newest-full-wins
  logic.

A delta whose parent is not present locally is never written. The wrapper forces a full instead, so primary can never
hold an orphan.

**supervisor's Go `gfsThin` is a fourth pruner.** It thins tertiary's snapshots, and it thins any secondary dir whose
module has no executable `backup.sh`, silently and chain-blind. That covers a module mid-uninstall, or one moved
between hosts, as sonarr and sabnzbd have been. It either learns the same keep rule (manifest parents, anchor, drill
gating), or it refuses any dir holding a `.meta/manifest.json` and says so. The refusal is the smaller change and is
enough, because every module that writes manifests ships its own `backup.sh`. *Resolved in R1 (2026-11-03): `gfsThin` is deleted and the Go keep-set serves tertiary and every secondary dir.*

Window changes, measured against today's sizes (influxdb3 full 177M, growing about 20M a week):

| Module | Now | Proposed |
|---|---|---|
| influxdb3 | retain 7d, weekly 4, monthly 3 | retain 14d, weekly 8, monthly 12: about 2.5G on `/share/30`, and it is the estate's history. Its full moves to the first run of each ISO week (§5a), so the longer retain no longer stretches the full cadence |
| others | unchanged | unchanged. They are small or already at 1200 monthly |

### 4. Restore gains modes and walks chains

```
restore.sh [--mode=replace|merge|drill] [--from=<run>] [--file=<path>] [--source=<dir>] [--keep-scratch] [--force] [--no-backup]
```

The wrapper resolves the **chain**, not one artifact: the full named by the target run's manifest plus every delta up to
it. It searches primary, then secondary (`/share/<index>0/backup/<svc>`), then tertiary, or only `--source` when given (a
directory of runs pinned outside the stages, as this incident's is). `--file` stays for a single artifact from anywhere
else. Each artifact passes `gzip -t` before anything is staged. As today, a bare run prints the plan and only `--force`
applies it.

| Mode | Touches live? | Needs | Use |
|---|---|---|---|
| `replace` | yes, stop or running per `RESTORE_SERVICE_STATE` | `restore_applied` (today's hook) | Wholesale rollback |
| `merge` | yes, additively | `backup_fingerprinted`, `restore_staged`, `restore_merged` | Put back history the live service lost, keeping what it has written since. influxdb3 only, see *Fit across modules* |
| `drill` | no | `backup_fingerprinted`, `restore_staged` | Prove a backup restores and holds at least its manifest's count for every closed unit |

A module that defines none of the new hooks keeps today's behaviour, and `merge` and `drill` refuse by name.

#### Invariants, and who enforces them

These are the rules the 2026-10-27 tests established (see *Recovering this incident* and *Pressure test*). The
wrapper, or `install.sh` where marked, holds all but the last two, so a module cannot skip one.

| Invariant | Enforced by | How |
|---|---|---|
| Scratch is read-only | wrapper | Fingerprints scratch straight after staging, before any other hook runs, then calls `restore_sealed` and fingerprints again. A sealed scratch whose fingerprint moved is a fault |
| Never restore into live and replay on top | wrapper | `merge` never calls `restore_applied`. For a module that has `merge`, `replace` refuses while live holds units newer than the backup, and names `merge` as the alternative. For a snapshot module, live is always newer, so the plan lists what `replace` will discard and `--force` applies it |
| Verify after a restart, not after the write | wrapper | Restarts live through its compose before fingerprinting it again |
| Merge only what live lacks | wrapper | Diffs the two fingerprints and hands `restore_merged` every closed unit present in staged whose count differs from live's, not only where staged > live. A boundary day where live has more rows but is missing some of staged's must still merge, and the merge is idempotent. A unit only live holds is never planned. Verify is `L' >= S` per planned unit |
| Never install over a state nothing judged | `install.sh` | A pre-install backup that comes back `regressed` abandons the install, like a failed one does. So does a skipped one: today `run_backup` skips when the container is not running and installs anyway. The only skips left are a first install (no current home) and a reinstall of the running version. `FAB_FORCE_INSTALL=1` overrides both, for a release that is itself the repair. On 22 Oct, 1848 and 1849 installed with no pre-install backup, and 1850 and 1851 over regressed ones. The guard would have stopped 1848, the first |
| Never restore a regressed run by default | wrapper | `--from` defaults to the newest **accepted** run, never a `regressed` one, and naming a regressed run needs `--force`. A delta restores the source's whole state, not a diff (*Pressure test*), so restoring the post-loss delta would have wiped history |
| One actor per module at a time | wrapper | `backup.sh`, `restore.sh` and `install.sh` take the same per-module `flock`. Today nothing locks, so a nightly stage, a release and a restore can interleave. The restore's own safety backup runs with pruning off, so it cannot prune the chain being restored |
| A snapshot replace leaves nothing newer behind | wrapper | `restore_files` moves each declared include to `/home/asystem/<svc>/replaced/<run>/` before extracting, then carries back only entries matching the module's excludes, never SQLite sidecars (§8). So files created after the backup, and foreign WAL files, cannot survive it |
| Dependents are quiet during a replace | wrapper | `replace` stops the module's run dependents (the modules whose `.env` carries its connection vars: HA and mlflow for postgres, weewx for mariadb) and starts them afterwards |
| Interrupted merges resume | wrapper | Records each finished unit in the restore run dir and skips it on a rerun |
| Rerun is harmless | contract | `restore_merged` must be idempotent, as influxdb3 line protocol is |
| Tags stay tags, time stays integer ns | influxdb3 hook | Tag set derived from `information_schema` (the `Dictionary` columns), never listed by hand; time selected as `CAST(time AS BIGINT)` |

#### Hooks

```
backup_fingerprinted  $1 = service address; print "<unit> <count>" per unit. The same hook fingerprints a backup at
                      write time, scratch, and live, so the three are always comparable
restore_staged        bring the resolved chain up in container <module>_restore, data under
                      /home/asystem/<svc>/restore/<run>, loopback on a free port; print its address
restore_sealed        optional; make scratch refuse writes
restore_merged        $1 = unit, $2 = scratch address; copy that unit into live
```

The wrapper tears scratch down on exit, unless `--keep-scratch` is given.

#### Flow

```
resolve chain      full + deltas up to --from; gzip -t each
safety backup      of live (existing step)
restore_staged     scratch up with the chain restored
fingerprint S      scratch; every closed unit must hold at least the manifest's count (pre-manifest runs skip this)
restore_sealed     scratch now refuses writes
                   ── drill ends here: teardown, publish the drill state
fingerprint L      live
plan               closed units present in S whose count differs from L, printed; without --force stop here
restore_merged     per planned unit, progress recorded
restart live       stop/start through the module's compose
fingerprint L'     every planned unit must have L' >= S, else fault naming the short units
teardown           scratch container and data dir
```

| Module | `backup_fingerprinted` unit | `restore_sealed` | `restore_merged` |
|---|---|---|---|
| influxdb3 | `<table>/<day>` rows | re-run scratch with `--mode query` on the same data dir | Export the day from scratch as jsonl (`--format jsonl` emits blank lines, so skip them), convert to line protocol, and write to live's `/api/v3/write_lp?precision=nanosecond` in chunks. The conversion is a small Python script the hook pipes through, with tag escaping and null or empty tags left out of the series key |
| postgres, mariadb | wrapper default for a SQL dump | `default_transaction_read_only` / `SET GLOBAL read_only` on scratch | None, so `replace` and `drill` only. See *Fit across modules* |
| plex, letsencrypt, wrangle, zigbee2mqtt, homeassistant | wrapper default for an archive | wrapper default, `chmod -R a-w` | None, so `replace` and `drill` only |

#### Fit across modules

Checked against every enrolled module on 2026-10-27. The manifest, chain-aware pruner, anchor and release drill apply
to all of them unchanged: every module but influxdb3 writes only fulls, so for them the chain closure is a no-op. Three
parts of the model, as first written for influxdb3, do not generalise and are restated here.

**1. Staging is not always a second running instance.** influxdb3, postgres (TimescaleDB image) and mariadb stage as a
scratch container on loopback. Four modules must never run a second copy:

- plex: `Preferences.xml` carries the server's plex.tv identity;
- zigbee2mqtt: it claims the USB coordinator and publishes on the live broker;
- letsencrypt: it could renew against the ACME account;
- homeassistant: it would claim the same integrations, devices and cloud links (§8).

For those, the wrapper's default staging extracts the archive into the scratch dir and seals it with `chmod -R a-w`.
That alone proves the artifact extracts, symlinks included. A module adds a drill check only where a real mechanism
can produce an artifact that extracts but is unusable:

| Module | Staged as | Drill check | Fingerprint units |
|---|---|---|---|
| plex | directory (514M archive, 684M extracted, 4s) | `PRAGMA integrity_check` on both `Plug-in Support/Databases/*.db`, run with the image's own `/usr/lib/plexmediaserver/Plex SQLite` in a throwaway `--network none` container that never starts the server. The host's `sqlite3` cannot open them (`unknown tokenizer: collating`). This is the only plex-specific code: the snippet copies the running configuration when `docker stop` fails, and a SQLite file copied mid-write can be torn where `gzip -t` cannot see it | the wrapper's default for a `backup_files` module, files and bytes per include. No plex hook |
| zigbee2mqtt | directory (16K zip) | none. The zip comes from zigbee2mqtt's own backup API, which writes it consistently, and the wrapper already runs `unzip -t` | wrapper default |
| letsencrypt | directory (28K) | none. The copy is of files certbot only rewrites at renewal, and every cert is reissuable from the DNS challenge anyway | wrapper default |
| wrangle | directory (5.4M) | none. The copy is taken under wrangle's own run lock, so it cannot catch a half-written file | wrapper default |

Only plex keeps a module drill check. letsencrypt, wrangle and zigbee2mqtt need no new code at all.

**2. Merge is for influxdb3 only. Every other module, postgres and mariadb included, is `replace` plus `drill`.**

A module earns merge only when both of these hold:

- **It can lose history silently while staying up.** influxdb3 did: PachaTree reset its index and served an empty past
  with a healthy status. postgres and mariadb fsync their WAL and redo logs, so a power cut leaves them consistent or
  refusing to start. Neither one comes up quietly missing last month. When either fails, the restore is a `replace`
  from the last nightly dump, which loses at most a day, and the wrapper's safety dump of live is taken first.
- **Its data merges without knowing the schema.** influxdb3's data model is the merge key, series plus time, for
  every table alike. A general relational schema has no such key. Merging it needs a per-table spec: natural key,
  surrogate columns to drop, foreign keys to remap through a parent's natural key, and derived tables to rebuild
  rather than copy. That spec has to be kept in step with schemas the module does not own (HA's recorder, weewx,
  mlflow). A blanket `INSERT … ON CONFLICT DO NOTHING` is wrong: with surrogate keys it silently drops backup rows
  whose id live has since reused.

**The rule: merge is offered only to modules with incremental backups**, and the build enforces it. A module that
defines `restore_merged` without emitting deltas fails `fab generate`. A snapshot module's backup is self-contained,
so `replace` restores it completely. A chain is the case where live keeps running past the newest full and drifts
from what the backup holds, and that drift is the only thing merge exists to reconcile. Today the rule and the two
properties above pick out the same module, influxdb3.

Drill on release and the regression guard are not part of "merge", and they apply to every module, snapshot or
incremental.

The checked tables are kept as the record of why, and as the starting point if a module ever does qualify:

| Table | Shape | What a merge would need |
|---|---|---|
| mariadb `weewx.archive` | PK `dateTime` | Clean: `INSERT IGNORE` on `dateTime` |
| mariadb `weewx.archive_day_*` | daily summaries derived from `archive` | Never copied; rebuilt with weewx's daily-summary rebuild |
| postgres `hass.statistics` | PK `id` serial, unique `(metadata_id, start_ts)`, `metadata_id` → `statistics_meta(id)` | `statistics_meta` merged first on `statistic_id`, then `id` dropped and `metadata_id` remapped |
| postgres `hass` recorder tables (`states`, `events`, `state_attributes`, `event_data`, `statistics_short_term`) | data excluded from the dump | Nothing |
| postgres `mlflow` | empty today | Unknown |
| postgres `wrangle` | not in the dump | Nothing; wrangle rebuilds it |

**3. A fingerprint has to come from the artifact, cover only closed units, and skip what legitimately expires.**

- **From the artifact, or from live's closed units.** Counting a unit live is still writing races the dump.
  postgres counts `COPY` data lines per table from the dump stream as it is gzipped, which is exact and free.
  mariadb's extended inserts cannot be counted cheaply, so it counts bytes per database between the dump's
  `-- Current Database:` markers instead, which is also free. influxdb3 counts rows per table per closed day on live,
  in seconds of queries. A past day does not change, so the count cannot race the backup. At the 08:11 backup on 22 Oct,
  live held only 96 rows, all in the open day, so every closed day from 13 Aug to 21 Oct counted zero against the
  previous manifest. The guard fires at the first post-loss backup, the same moment a nightly restore would have
  caught it. Whether the backup actually holds those rows is the drill's job: on release and in the GFS-synced weekly drill, the staged
  chain must hold at least the manifest's count for every closed day.
- **Closed units only.** Today's influxdb3 day and today's `weewx.archive` day are still being written. Fingerprints
  record them, but the shrink guard and the merge planner ignore any unit not older than the run's own timestamp
  minus one unit.
- **Expiry.** Each module declares its durable units, and the regression guard compares only those. Everything else
  is reported, never guarded. With the wrapper defaults, every unit is durable unless the module says otherwise, and
  the 20% shrink threshold absorbs ordinary churn. The exceptions are influxdb3 days outside the database's retention
  (`home` has none, `_internal` 7 days), and in postgres the recorder tables, whose data is excluded from the dump.

#### What each module writes

| Module | Restore | New code |
|---|---|---|
| influxdb3 | `replace`, `merge`, `drill` | fingerprint, staging, sealing, merge |
| postgres | `replace`, `drill` | staging (load into scratch) and the TimescaleDB-aware `restore_applied` from *Pressure test* |
| mariadb | `replace`, `drill` | staging (load into scratch, waiting for init) |
| plex | `replace`, `drill` | one drill check (`Plex SQLite` integrity) |
| letsencrypt, wrangle, zigbee2mqtt | `replace`, `drill` | none |
| homeassistant | `replace`, `drill` | enrolment only: a `backup_files` `backup.sh` and `restore_files` `restore.sh`, plus `HOMEASSISTANT_BACKUP_LIVE=atomic` for the tar retry. No hooks (§8) |

#### Pressure test, 2026-10-27

Every enrolled backup was drilled by hand against its newest artifact, and all scratch was removed afterwards.

| Module | Result | What it changes |
|---|---|---|
| influxdb3 | The post-loss `delta-2026-10-22_08-11-23`, restored on top of the good chain, leaves **96 rows** from 22 Oct 00:09Z. The 4.9M rows before it are gone | A delta restores the source's whole state, not a diff. At 08:11 live's 96 rows were all in the open day, so every closed day counted on live was zero: the closed-day fingerprint catches the loss at the first post-loss backup, with no nightly restore. It also means restoring the newest run is dangerous by default, hence the regressed-run invariant |
| postgres | **`restore_applied` has never worked.** The dump's globals start with `CREATE ROLE postgres`, which exists in any running cluster, so `ON_ERROR_STOP=1` aborts at line 1. Once past that, the load still fails, because the image ships TimescaleDB 2.30.2 while every live database is on extension **2.27.2**. A bare `CREATE EXTENSION timescaledb` builds a 2.30.2 catalog that the 2.27.2 `COPY`s do not fit. It loads cleanly in 10s with: the `CREATE ROLE postgres;` line dropped; `CREATE EXTENSION timescaledb WITH SCHEMA public VERSION '<dump's>'` then `SELECT public.timescaledb_pre_restore();` per database, with `public.timescaledb_post_restore()` before the next `\connect` (pg_dump empties `search_path`); and the extension first dropped from any database scratch's image init created. All 10 tables with data match the dump's `COPY` line counts exactly | `restore_applied` is rewritten around that transform. `replace` into live also needs each dumped database dropped first, because `pg_dump --create` emits `CREATE DATABASE`. The manifest records each database's `extversion`. The extension skew is itself a latent fault, and its cause is now known. The cluster was initialised on 8 Jun 2026 13:54, the day the image moved to `2.27.2-pg18`. The image's `000_install_timescaledb.sh` runs only on an empty data dir, and `bootstrap.sh` created `hass`, `mlflow` and `wrangle` from `template1`, so all five databases began at 2.27.2. Nothing has run `ALTER EXTENSION timescaledb UPDATE` since. Nine image bumps changed only the default version, and the loader keeps loading `timescaledb-2.27.2.so`, which today's image still ships (it carries 2.23.0 → 2.30.2). The fix is for postgres's bootstrap, which runs on every release, to update each database whose `extversion` differs from `default_version`, each in its own `psql -X` session. Tested on a scratch copy of every database: about 150ms each, 2.27.2 → 2.30.2, and row counts and compressed chunks unchanged, `wrangle`'s hypertables included |
| postgres | `pg_stat_user_tables` estimated `hass.statistics` at 124,833 rows; it holds 3,318,833 | Never fingerprint from planner statistics. mariadb's estimate was also off (15,335 against 17,700) |
| mariadb | Loads in 19s. All 115 `weewx` tables are present, none with more rows than live, and `archive` has 17,700 against 17,822 live. The image's entrypoint answers `ping` from a **temporary init server**, and loading against that broke init | `restore_staged` waits for `init process done`, then the final server, never the first ping |
| plex | Both databases pass `integrity_check`, but only with `Plex SQLite` | Restore stays a straight snapshot `replace`. The drill is extract plus that one check, and the fingerprint is the wrapper default |
| zigbee2mqtt | The zip holds `configuration.yaml`, `database.db` (53 devices), `coordinator_backup.json` (parses, open-coordinator-backup format), `devices.yaml`, `groups.yaml` and `state.json` | Default staging only; no check |
| letsencrypt | `live/` symlinks survive into `archive/`, and the cert is valid to Jan 2027 | Default staging only; no check |
| wrangle | The history files parse | Default staging only; no check |
| supervisor | *Retracted.* A first reading said the 27 Oct nightly run stopped on all five hosts, at "promoting [supervisor] [1/N]". It did not. Every host's local `/home/asystem/supervisor/backup/2026-10-27_*/status.json` reads `success`, tertiary included. The misreading came from secondary: it promotes the run tree to the share *while that run is still running*, so the share copy of the current run always ends at that line, without `status.json`, until the next night re-copies it | Anything that judges a run reads the **local** run tree, never the share copy, which is a night behind by design. The rule that a run with no `status.json` after its timeout is a failure stays, applied to the local tree |
| coverage | *Decided 2026-10-27:* homeassistant is enrolled (§8). **sonarr and sabnzbd are not enrolled, on either host, and their duplicate homes on may and mad are left as they are**, because losing either costs no data: the media folders hold the real data, so sonarr's `sonarr.db` is rebuilt by re-adding the series and rescanning them, with its settings re-entered by hand, and sabnzbd's `history1.db` is download history that nothing later depends on. The shares' guest `0777` permissions are accepted as they are, with HA's tokens and letsencrypt's private key on them. Measured at the time: Not enrolled, but holding state git cannot rebuild: homeassistant `.storage` (9.2M, measured; 22M was the whole config dir: registries, auth, and the UI-configured integrations, influxdb included per `configuration.yaml`), sonarr `sonarr.db` (147M on may), and sabnzbd `history1.db`. sonarr and sabnzbd have homes on both may and mad | homeassistant is enrolled (§8). sonarr and sabnzbd stay out, for the reason recorded with the decision |

**Second round, testing the assumptions the design added:**

| Assumption | Measured | Verdict |
|---|---|---|
| Archive entries are stable night to night | Over the last 7 nights: plex, letsencrypt and zigbee2mqtt lost no entries. wrangle lost 6–21 a night, all versioned bank files | Per-file units are wrong. Units are per include for `backup_files` modules, and per entry only for API-written archives |
| Include totals move less than the shrink threshold | The worst nightly drop was wrangle `bank` at −10.7% (24,344K → 21,736K). plex moved ±0.6%, letsencrypt 0% | 20% on the module total holds. Never apply it per unit |
| A closed influxdb3 day never changes | `full-2026-10-26` plus the 27 Oct delta, staged, against live about 10 hours later: all **167** table/day units for 22–25 Oct identical. Counting every table on live took 5s. wrangle writes postgres, not influxdb3, so no writer backfills old days | Live closed-day fingerprints are sound |
| Sidecars can sit beside the archive | Three readers take the first file in the run dir as the artifact | `.meta/`, plus name-pattern selection (§1) |
| One pruner owns every keep decision | supervisor's `gfsThin` thins tertiary snapshots and any secondary dir without an executable `backup.sh` | Refuses manifest-bearing dirs (§3). Superseded in R1: `gfsThin` is deleted and the Go keep-set serves every dir |
| A missed Monday is harmless | A missed drill left its point counting for nothing forever | Catch-up drills (§5a) |
| A pre-install backup protects the install | It runs and passes on a regressed state, and `install.sh` skips it, then installs anyway, when the container is down | A regressed or skipped pre-install backup aborts the install (invariants) |

**Third round, testing §7, §8 and wholesale replace:**

| Assumption | Measured | Verdict |
|---|---|---|
| A running HA copy cannot fail | HA writes temp files in `.storage` and renames them. tar against that pattern exited 1 in 34 of 200 runs, which `pipefail` plus `2>/dev/null` turns into failed backups with no reason. 120 runs against live HA saw no failure, but HA wrote nothing in those 2 minutes | Exclude `tmp*`, retry exit 1 for atomic writers, log tar's stderr (§8) |
| `--warning` flags can silence it | They hide the message only. Exit status stays 1 | Retry, not flags |
| Wholesale replace loses nothing that should stay | plex keeps 8 rotated database copies (about 2.9G) inside its include, under an exclude | Carry excluded entries back (§8) |
| Today's restore is safe for plex | The archive has no `-wal`/`-shm`; live does. Extract-over leaves a foreign WAL beside the restored databases | Fixed by wholesale replace; sidecars never carried back |
| The extension update is invisible to clients | Sessions holding the old library are killed on their next TimescaleDB query; jobs survive | One forced reconnect per image bump (§7) |
| `<home>/restore/replaced-<run>/` is a safe place for the moved copy | Under the swept scratch path, inside the data dir | `/home/asystem/<svc>/replaced/<run>/` |

wrangle needs nothing of its own: its restore is a plain snapshot `replace`, and its drill and fingerprint are the
wrapper defaults.

Drill cost per release is small everywhere: influxdb3 about 7s for the full plus seconds per delta, postgres 10s,
mariadb 19s, and plex 4s to extract. meg has the least headroom, with 3G available.

#### Settled 2026-10-27

1. **`--mode query` serves restored data and refuses writes.** A chain restored in the default mode and then restarted
   with `--mode query` (scratch dropped and re-run on the same data dir, about 4s) served all 4,907,096
   `sensor__temperature` rows over the same range. A write got HTTP 500 "cannot write to a read-only server: must enable
   ingest mode", and nothing landed. So influxdb3's `restore_sealed` is: restore in the default mode, then re-run
   scratch with `--mode query`.
2. **The live restart costs supervisor a few seconds of metrics, and HA nothing.** A graceful stop and start of the same
   image on the same data size took 1.7s three times running (stop 0.7–0.8s), and live's own startups logged
   0.9–3.6s to ready. The entrypoint's node stages are skipped on live, because its node dir is `cluster_1/node_1`, not
   `node_1`. How each writer handles the gap:
   - HA (`max_retries: 3`) retries a batch every `RETRY_DELAY` 20s and keeps its queue for `QUEUE_BACKLOG_SECONDS`
     30s plus the retries, so it rides out anything under about 20s. Its log shows `Catching up, dropped` if not.
   - supervisor (`engine_util_database.go`) retries once after 500ms, then drops the batch. A restart therefore loses
     every supervisor point due inside the gap, on every host. That is the same cost as every influxdb3 release, which
     restarts it the same way, so the merge accepts it. If it ever needs fixing, it is fixed in supervisor's
     retries, not here.

### 5. Releases exercise it

`install.sh` already takes a backup before installing. After `start_service` it then runs:

```
restore.sh --mode=drill --from=<the pre-install run>
```

A drill failure is a release warning, not an abort, because the new version is already running. It publishes a
`drill` state to the backup metrics, so a broken backup surfaces on the next release rather than the next outage. A
`FAB_SKIP_DRILL=1` escape is there for large modules mid-iteration.

### 5a. Weekly drills, in step with GFS

The weekly drill is part of secondary's GFS pass, not a separate schedule, so every sparse point GFS keeps is a point
that has been shown to restore.

- **When.** On the first nightly run of each ISO week (Monday, Perth), supervisor's secondary stage drills the
  previous week's weekly point **before** that night's `--prune-gfs`. Every run also catches up: it drills every
  settled sparse point that has no `.meta/secondary/drill.json`. A Monday lost to an outage or a hung run is
  then drilled the next night instead of never. On the first run of a month, it also drills
  the previous month's point, if that was not already the weekly one (a month that ends mid-week). That is the moment a
  point settles: GFS keeps the newest full in each ISO week and month, and for a module that takes a full every night,
  the newest full is only final once its bucket has closed.
- **What.** `restore.sh --mode=drill --from=<point> --source=/share/<index>0/backup/<svc>`, on the module's own host,
  which has its image. It holds the module's `flock`, like every other actor.
- **Where the result lives.** Supervisor writes `<run>/.meta/secondary/drill.json` into the drilled run's secondary dir,
  and publishes the `drill` state. Tertiary mirrors it alongside the run, so the verdict travels with the artifact.
  Each stage writes only under its own `.meta/<stage>/`, so promotion, which copies primary's run dirs onto the share
  with `rsync -a` and no `--delete`, can never overwrite the weekly verdict.
- **It shows in `backup tail`.** The drill runs inside secondary, so supervisor logs one line per drilled point into
  `run.log` (`drilled [<svc>] point [<run>] as [success|failure] in [<s>] s`). A failure adds the first fault line
  from `restore.sh`, with the path of the drill's full `output.log`. A failed drill fails the secondary stage, so
  the summary row's secondary cell and the run's result read failure. Catch-up drills log the same way.
- **Release drills reach it too.** `install.sh`'s post-start drill (§5) is not a supervisor run, so it records its
  verdict in the pre-install run's `.meta/primary/drill.json`. The next nightly primary stage logs
  every release drill recorded since the previous run (`release drill of [<svc>] point [<run>] as […]`), and a
  failed one fails that stage. The release itself already prints the result as it happens.
- **How pruning uses it.** A sparse point counts towards its tier's quota only once its `secondary/drill.json` is green.
  A release drill's `primary/drill.json` is logged but never counts here. A point
  whose drill failed, or never ran because the run hung, is kept but counts for nothing. So the tier keeps reaching
  back, and **the oldest drilled point of a tier is never pruned until a newer one has drilled green.** A failed drill
  also publishes `drill` failed and counts as a failed stage in `Fail BKP` until a later drill of that module is
  green, as for `regressed` (§2), and the point is never pruned while it is the newest of its bucket, so it stays
  for diagnosis.
- **Cost per week, measured on the pressure test:** influxdb3 drills a full alone (about 7s, growing with history),
  postgres 10s, mariadb 19s, plex 4s to extract, and the small archives in a second or two. A weekly point is always a
  full, so influxdb3 never drills a week of deltas here; those are proven by release drills and by the next full.

**influxdb3's full follows the ISO week, not an age.** Today `backup_written` takes a full whenever the newest one is
older than `BACKUP_RETAIN_DAYS`, so the weekday drifts (Sat 26 Sep, Sun 4 Oct, then Mondays), and ISO week 41 got no
full and so no weekly point. Raising the window to 14 days (§3) would make every other week pointless. Instead, the
first run of each ISO week writes a full, and every other run writes a delta. `BACKUP_RETAIN_DAYS` then only governs
primary's window. Each week has exactly one weekly point, and Monday's drill finds it.

`retire_home` refuses to delete a home whose server-side backup store holds a run absent from secondary. This was the
copy that would have saved influxdb3 had secondary not had it.

### 6. Durability

- **Drop `commit=600`** in the four `fstab` sources: `src/{may/_debian_may,meg/_debian_meg,jil/_debian_jil,max/_fedora_max}/src/main/resources/fstab`.
  It is a mount option change, so applying it needs a remount or reboot per host, nothing more.
- **UPS + NUT** on the server hosts, as `filesystem.md` already says, so a clean shutdown runs at low battery.
- **influxdb3 `entrypoint.sh`**: move empty files to `cv2/quarantine/<ts>/` instead of deleting them. **Refuse to start**
  if that would leave no non-empty checkpoint (or no manifest), and print what was found. The operator then
  restores rather than unknowingly resetting. Report the missing fsync to InfluxData with the empty files as evidence.
- The influxdb3 healthcheck adds a cheap floor: `min(time)` of a sentinel table must not move later between
  checks. That catches the same fault within minutes instead of at the next backup.

### 7. postgres: TimescaleDB currency and the bootstrap source

Two changes to `src/mad/postgres`, both found while investigating the extension skew (*Pressure test*).

**1. Restore the bootstrap source to a fragment.** Since 8 Jun (`af22a3d89`, release 10.200.1028),
`src/build/resources/bootstrap.sh` has held a whole generated script instead of the snippet
`write_container_bootstrap()` wraps. It starts with a stray `bash#!/usr/bin/env bash`, then the "written by the build
process" banner and the old `while ! checkalive.sh` wait loop. So the generated `src/main/resources/image/bootstrap.sh`
nests the old wrapper inside the new one: the banner twice, two wait loops, and a first line bash runs as the command
`bash#!/usr/bin/env`. The source goes back to the fragment alone, from `psql_su() {` to the last `init_user_database`
call. No other module is affected (checked by the `bash` prefix across every `src/build/resources/bootstrap.sh`).

**2. Keep every database's extension at the image's version.** Appended to the fragment, after the users and
databases exist:

```
for each database that allows connections (template1 included, so new databases inherit the current version):
  if extversion <> default_version for timescaledb:
    psql -X -d <database> -v ON_ERROR_STOP=1 -c 'ALTER EXTENSION timescaledb UPDATE'
  print the database, the version before and after
```

- One `psql -X` invocation per database. TimescaleDB requires the update as the first command of a fresh session,
  before anything has loaded the old library, and `-X` keeps a `psqlrc` from running first.
- **Every other session that loaded the old library is killed on its next TimescaleDB query** (round 3, on a scratch
  copy of `wrangle`: `FATAL: "timescaledb" already loaded with a different version … The session will be
  restarted`). The update itself took 143ms, both compression jobs survived, and the background-worker scheduler
  restarted itself. By the time the bootstrap runs, HA's recorder, mlflow and any wrangle job have reconnected after
  the release's restart, so each takes one more forced disconnect. That happens once per image bump, not every
  release, since the update only runs when the versions differ. HA's recorder retries a failed commit, so confirm
  in its log on the first run that nothing was dropped, as for the influxdb3 restart.
- **A `replace` runs the same update afterwards.** A dump restores at its own extension version (below), so restoring
  an older dump would otherwise leave the databases skewed until the next release.
- It runs on every release, after the pre-install backup, so a failed update rolls back to that backup.
- The databases are compared one by one, so a database already current is left alone, and a rerun is a no-op.
- `default_version` comes from the image (`pg_available_extensions`), so no version is written in the script, and the
  next image bump is picked up by its own release.
- Tested 2026-10-27 on scratch copies of all five databases: about 150ms each, 2.27.2 → 2.30.2, with row counts and
  compressed chunks unchanged, `wrangle`'s hypertables included. In the test, `wrangle` was created from `template0`.
  Created from an already-updated `template1`, it inherits the new version and a 2.27.2 dump will not load into it,
  which is the restore transform's concern below.

**What it changes for restore.** The TimescaleDB-aware `restore_applied` (*Pressure test*) creates the extension at the
**dump's** version, read from the dump's databases and recorded in the manifest as `extversion` per database, never
hardcoded. Once the bootstrap has run, new dumps record 2.30.2. Old dumps still record 2.27.2, which the image can load
only while it ships that library. So a restore of a dump whose version the image no longer ships fails by name in its
plan, before anything changes, and names the last image that does. The GFS-synced drills (§5a) are what surface that
before it is needed: a monthly point that stops drilling green says the image has outgrown it.

### 8. homeassistant: enrol `.storage` as a snapshot replace

HA has never been backed up. Its config dir, `/home/asystem/homeassistant/latest` on meg, mixes three kinds of entry,
and only the first needs a backup:

| Kind | Entries | Why |
|---|---|---|
| **State git cannot rebuild** (the includes) | `.storage` (9.2M: entity, device and area registries, `core.config_entries` with every UI-configured integration including influxdb, `auth`, `person`, `core.restore_state`, `lovelace_dashboards`, `homeassistant.exposed_entities`, `trace.saved_traces`), `custom_templates`, `blueprints` | Written by HA at run time. `blueprints` holds only HA's defaults today, but it is where an imported blueprint lands, and it is 44K |
| From the repo, rewritten every release | `automations.yaml`, `configuration.yaml`, `customise.yaml`, `custom_components`, `custom_config`, `custom_packages` (including the generated `custom_packages/scripts.yaml`), `hass-entities.yaml`, `network_devices.json`, `ui-lovelace*`, `www`, `.google_service_account.json`, the health-check scripts | Excluded. `install.sh` copies `data/*` over the home on every release |
| Leftovers nothing writes or reads any more (tested 2026-10-27) | `checkready.sh` (mtime 2025-10), `influxdb-ignores.yaml` (2026-08-13, superseded by `custom_config/influxdb/ignore_*.yaml`), `ui-panel-custom.yaml` (deleted from the repo in `385556fdb`, 2026-03-22), top-level `scripts.yaml` (2024-10, the generator now writes `custom_packages/scripts.yaml`), `entities.yaml` (0 bytes), `python_scripts/` (empty) | Deleted in phase 1c, before enrolment. None is in the release package, none is referenced by `configuration.yaml` or any included file, and no asystem code writes it. HA's UI script editor still saves to the fixed top-level `scripts.yaml` (`SCRIPT_CONFIG_PATH`), so a save would recreate it, but `configuration.yaml` loads scripts only through `custom_packages`, so a script saved there would never load. Nothing has saved one since 2024-10. The home copy carries every file forward on each release, which is the only reason they exist. (`configuration.yaml`'s apparent `entities.yaml` reference is `hass-entities.yaml`) |
| Runtime, regenerable | `.HA_VERSION`, `.cache`, `.cloud`, `.ha_run.lock`, `deps`, `tts`, `home-assistant.log*` | Excluded |

Inside `.storage`, HA's two stale one-off migration copies, `core.entity_registry.bak-20261009140938` (3.4M, from
the 9 Oct registry flush) and `core.device_registry.20260810_040425.migration_backup`, are deleted in phase 1c before
the first backup. Inside `.storage`, the only excludes are HA's temp files and any future migration copies (below).

- **Backup** is a `backup_files "." HOMEASSISTANT_BACKUP_INCLUDES HOMEASSISTANT_BACKUP_EXCLUDES` snippet, enrolled in
  `generate.py` with `write_container_backup()` and `write_container_restore()`, as letsencrypt does. **HA keeps
  running**: it writes each `.storage` file atomically, so a copy can never catch a half-written one, and stopping HA
  nightly would pause every automation. HA 2026.10's `write_utf8_file` writes a `NamedTemporaryFile` in `.storage`
  itself, then `os.replace`s it over the store. The most a running copy can miss is a store still in its write
  delay, about 10s of changes.
- **A running copy makes tar exit 1, and that has to be handled, not hidden** (round 3). Racing tar against that
  exact write pattern failed 34 of 200 runs: a temp file removed mid-scan, a temp file changing, or `.storage`'s own
  mtime moving. `backup_files` runs tar with `2>/dev/null` under `pipefail`, so each of those is a failed backup
  with no reason given. `--warning=no-file-*` only hides the message; the exit status stays 1. The measured fix:
  - exclude `.storage/tmp*`, which cuts failures to 3 in 120, all the directory mtime;
  - a module that declares its writer atomic (`<MODULE>_BACKUP_LIVE=atomic`, HA only) retries tar's exit 1 up to 3
    times, 10s apart. That is about 1 in 60,000 against a writer far busier than HA. Exit 2 fails at once. A store
    renamed over while tar reads it still archives a whole old version, because nothing writes in place;
  - `backup_files` sends tar's stderr to the run log, for every module, instead of `/dev/null`.
- **HA writes new migration copies on its own upgrades**, as it did on 10 Aug and 9 Oct. Deleting the two stale ones
  (above) does not stop the next. So `.storage/*.bak-*` and `.storage/*.migration_backup` are also excludes. That
  keeps a 3.4M copy appearing, then being deleted, from swinging the module total past the 20% shrink threshold.
- **Restore** is a straight snapshot `replace` with `RESTORE_SERVICE_STATE="stopped"`: stop HA, replace the three
  includes wholesale (below), and start it. HA rereads its registries and config entries on start.
- **Drill** is the wrapper default: extract read-only into scratch. HA is never started on it, since a second HA would
  claim the same integrations, devices and cloud links. **Fingerprint** is the default, bytes per include. A
  registry that shrinks by more than 20% of the module's total is flagged.
- **Retention**: `HOMEASSISTANT_BACKUP_KEEP_MONTHLY=1200`, like the other small modules. The archive is a few MB.
- **The archive is sensitive.** `auth` holds refresh tokens and password hashes, and `core.config_entries` holds
  integration credentials (the influxdb token among them). That is true of letsencrypt's private key already. But
  the shares are guest-mounted CIFS with `dir_mode=0777`, so every backup on them is readable by any host that mounts
  the share. Decided 2026-10-27: that is accepted.

**Snapshot replace replaces each include wholesale, for every `backup_files` module.** Today `restore_files` extracts
over what is there, so anything created after the backup survives the restore. For HA, that is a store file for an
integration the restored `core.config_entries` no longer has. For wrangle, whose bank files are versioned, live's
newer `_sheet_bank_balances_v19.csv` stays beside the restored `v18`. If wrangle reads the newest version, the restore
silently does nothing. So `restore_files` first moves each declared include to
`/home/asystem/<svc>/replaced/<run>/`, then extracts. That is a sibling of the version homes on the same filesystem,
so the move is a rename. It is not under `restore/`, which the wrapper sweeps as stale scratch, and not inside the
home, where `backup_files` would report it as unmatched. The moved copy is the rollback beyond the safety backup, and
it is removed by the next successful backup.

Two refinements, from round 3:

- **Excluded entries under an include are carried back** from the moved copy after extracting, because the archive
  never had them. plex's `Plug-in Support` holds 8 of its own rotated database copies (`*.db-2026-10-17` … `-26`,
  about 2.9G), matched by its `*.db-YYYY-MM-DD` exclude. Without the carry-back, a restore would delete plex's own
  local rollback copies.
- **SQLite sidecars are never carried back:** `-wal`, `-shm`, `-journal`. The newest plex archive holds only the two
  `.db` files, while live has a `-wal` and `-shm` beside each. **Today's** extract-over restore would leave live's
  WAL beside the restored database, and SQLite replays a `-wal` on open, so a WAL from a different database state
  would be applied to it. Wholesale replace removes them with the include.

## Recovering this incident

Use the secondary chain. It is complete and passes `gzip -t`:

```
/share/30/backup/influxdb3/2026-10-19_01-00-28   full   177M
/share/30/backup/influxdb3/2026-10-19_22-25-53   delta  4.5M
/share/30/backup/influxdb3/2026-10-20_01-00-08   delta  4.8M
/share/30/backup/influxdb3/2026-10-21_01-00-08   delta  7.5M
/share/30/backup/influxdb3/2026-10-22_01-00-08   delta   11M
```

A copy of the chain, pinned outside every pruner, is at `/share/30/tmp/influxdb3-restore-2026-10-22/`. Once rollout phase 5
lands, the recovery is one command, run bare to read the plan, then again with `--force`:

```
/var/lib/asystem/install/influxdb3/latest/restore.sh --mode=merge --from=2026-10-22_01-00-08 --source=/share/30/tmp/influxdb3-restore-2026-10-22
```

The planned units should be every table's days from 2026-08-13 to 2026-10-21. Live has none of them, so the merged
range cannot overlap anything live has written.

**Drilled by hand on 2026-10-27, and it works.** This is the recipe `restore_staged` encodes:

- Data dir `/home/asystem/influxdb3/restore/drill-<ts>`, holding only a copy of the live `cluster_1/trial_or_home_license`.
  The Home licence verifies on a second instance with a fresh catalog. It binds `object_store_info`, which is a hash of
  the store type and the in-container path (`file`, `/asystem/mnt`), so the scratch mount must keep that path. Never pass
  `--license-email` to scratch: with no licence file, that would start the email verification.
- `docker run --name influxdb3_restore -p 127.0.0.1:18182:8181 --entrypoint influxdb3 <image> serve --node-id node_1
  --cluster-id cluster_1 --object-store file --data-dir /asystem/mnt --license-type home --without-auth
  --disable-telemetry-upload`. The module's `entrypoint.sh` is bypassed, and loopback plus no auth need no token.
- Extract the full into `cluster_1/backups/`, then `create restore --backup full-…`. Extract each delta into
  `backups/full-…/incremental/`, then `create restore --backup delta-…`, one at a time in order, polling
  `status restore --id` on its `Status:` line until it reads `completed`. The `Completed At:` label also matches
  "completed", so don't grep the whole output for it.
- Result: 2026-08-13T02:03Z → 2026-10-21T16:59Z, 70 consecutive days, and the same table set as live.
  `sensor__temperature` has 4,907,096 rows. The full took 7s for 2790 files and 331MB, and each delta a few seconds.
  The scratch data dir is 808M.

**Merge semantics, tested the same day** with one hour of `sensor__temperature` (3535 rows):

- **Rewriting deduplicates, on an instance that was never restored.** Writing the hour twice, plus a control row 1ns
  off, gives exactly 3536 rows and 3536 distinct timestamps. That holds before and after two clean restarts. A same-key
  write replaces the value (last write wins), and the 1ns control proves the count can see a duplicate.
- **The export must keep tags as tags and time as integer nanoseconds.** Tags are the `Dictionary(Int32, Utf8)`
  columns in `information_schema.columns`, and everything else is a field. Select `CAST(time AS BIGINT)`, because the
  text output drops sub-microsecond digits. Leave null or empty tags out of the series key. `--format jsonl` emits
  blank lines.
- **A restored instance silently drops new writes into restored day windows at its next restart**: HTTP 204,
  snapshotted, and gone after `gen0 restore-eviction`. Writes into a day the restore did not cover persist. So:
  - scratch is read-only. Never write into it, and fingerprint it before anything else touches it;
  - never merge by restoring into live and then replaying newer data on top;
  - the wrapper re-fingerprints live **after a restart**, not just after the write, since the post-write count
    alone would have passed here;
  - live itself was never restored, so this does not apply to the merge target. If a `create restore` ever runs on
    live, though, later backfills into restored days would vanish the same way. Report it to InfluxData along with the
    fsync fault.

## Rollout

### What can lose data during the rollout itself

| Risk | Why | Guard |
|---|---|---|
| A new pruner deletes what the old one kept | `install.sh` runs the **new** release's `backup.sh` for the pre-install backup, which prunes too, and supervisor's secondary stage calls that same script's `--prune-gfs`. New pruning code is live the moment a module installs | the pruner's brake and the comparison run, *Decided 2026-11-03* |
| A sidecar is read as the artifact | Three readers take the run dir's first file (§1) | The name-pattern selection ships in phase 3 before any manifest is written, and sidecars live in `.meta/` |
| A run without a manifest is misread | Every run before the rollout has none | No manifest means its parent is inferred by order, as GFS does today, and it is never deleted on manifest evidence. Its fingerprint is "unknown", which never triggers or releases an anchor |
| supervisor rejects an unknown backup state | `regressed` and `drill` are new words in a vocabulary `metric_schema.go` owns | supervisor releases first, with both words and the parity test |
| The influxdb3 restarts | each release, and the merge, restart it | Accepted: a few seconds of supervisor metrics, nothing from HA (*Settled 2026-10-27*) |
| The merge writes wrong data into live | it is the only step that writes history into production | Safety backup first, plan read before `--force`, verified after a restart. The pinned chain stays until a new full covers it |
| A plex restore before phase 4 corrupts its databases | Today's `restore_files` extracts over live, leaving live's `-wal`/`-shm` beside the restored `.db` files (§8, round 3) | Until phase 4 ships wholesale replace, a plex restore by hand stops plex, moves `Plug-in Support/Databases/*-wal` and `*-shm` aside, then runs `restore.sh`. Moving them while plex runs would leave it writing to an unlinked WAL |
| A bad prune anywhere | | tertiary's read-only snapshots, which every phase leaves untouched. Tertiary ran on every host every night through 27 Oct |

**Shadow pruning: dropped 2026-11-03.** It was the guard for new pruning code running in bash on every module the moment it installed, which no longer holds: the one pruner is Go in supervisor, released once, with a one-off read-only comparison against every host's run trees and snapshots instead of seven nights of logging. The standing backstop is tertiary's read-only snapshots, and the pruner adds a brake (*Decided 2026-11-03*). The shadow code that shipped in phase 3 (`backup_kept_next` and the `Prune disagreement` path) is deleted in R2 with the rest of the bash pruners.

### Phases

Each phase ends at its gate. Nothing in the next phase starts until the gate holds.

The incident chain's pin, phase 6 and the incident cleanup are done (3 Nov). Phases 7 to 9 are the Go engine releases (*Decided 2026-11-03*).

| Phase | Ship | Gate |
|---|---|---|
| 0 | ~~Pin the incident chain~~ Done: `/share/30/tmp/influxdb3-restore-2026-10-22/` | five runs, `cmp` and `gzip -t` clean |
| 1 Durability | Drop `commit=600` from the four `fstab` sources, and apply it with `mount -o remount,commit=5` on each mount (no reboot needed). influxdb3 `entrypoint.sh` quarantine-and-refuse | `findmnt -no OPTIONS` shows no `commit=600` on any host. A drill on scratch: zero-length checkpoints make the entrypoint refuse to start, with the quarantine dir populated |
| 1b postgres | §7: the bootstrap fragment restored, then the extension update added to it. One postgres release | Every database reports `extversion = default_version`. The generated `image/bootstrap.sh` holds the banner once. The pre-install backup taken just before this release stays as the rollback point until phase 4's drill of a post-update dump is green |
| 1c homeassistant | First, `backup_files`' tar changes, as a framework change: stderr to the run log, and the exit-1 retry for a module declaring `_BACKUP_LIVE=atomic`. Without them a running HA copy fails intermittently with no reason (§8, round 3). `backup_files` is inlined into each generated `backup.sh`, so regenerate every module, read every `backup.sh` diff, and release each module whose script changed (plex, letsencrypt and wrangle call it). Then stderr reaches the run log for every module once 1c lands, and phase 3's diffs hold only phase 3's change. Then delete the two stale `.storage` migration copies and the six tested leftovers (§8), and enrol `.storage`, `custom_templates` and `blueprints`, excluding `.storage/tmp*`, `*.bak-*` and `*.migration_backup`, in a homeassistant release. The enrolment is additive: it gains manifests in phase 3 like every other module | Every module whose `backup.sh` changed is released, and its next nightly run succeeds. The next nightly run shows homeassistant in primary and secondary. `backup_files` reports no unmatched entry. A bare `restore.sh` prints a plan naming exactly the three includes. The archive extracts into scratch |
| 2 supervisor | `regressed` and `drill` states in `metric_schema.go`, the shell mirror, the parity test. A `regressed` run feeds `BKP` (false) and `Fail BKP` (a failed stage); a failed drill feeds `Fail BKP` only (§5a). The two descriptions widen (§2). Primary reads a new run's `.meta/manifest.json` after the script exits, records `regressed` beside `SuccessBool`, which stays true so secondary still promotes, and writes the evidence lines to `run.log` (§2). Secondary logs `drilled [...]` per drilled point, and primary logs release drills from `.meta/primary/drill.json` (§5a). A failed drill holds `Fail BKP` non-zero across runs: each run reads the module's newest `.meta/secondary/drill.json`, not only its own roll-up, until a later drill is green. Report a run whose local `status.json` is missing after its timeout as failed. Also write a `failure` `status.json` for a service primary refuses before starting it (container not running, or `health: starting`), which today leaves its service dir empty and so no state at all (seen on `meg`'s `homeassistant`, 2026-10-28 09:14) | supervisor released to every host, parity test green, existing backup states unchanged in HA, a planted `regressed` run on a test module turns `BKP` false and `Fail BKP` non-zero, still reaches the share, and `backup tail` of that run shows `as [regressed]` with its evidence line and a failed result; the next skipped run of that module does not re-report it; a planted failed drill shows the same way in the secondary cell, and two consecutive nightly runs complete on every host with tertiary. **The failed-drill parts (drill verdicts feeding `Fail BKP`, `drilled [...]` and release-drill lines) were deferred to phase 9 (R3) on 2026-11-03: nothing writes or reads `drill.json` in Go until then** |
| 3 Backup side | Manifest, fingerprints, regression guard (report only: it publishes `regressed` and pins an anchor, but nothing waits on `--accept`), chain-aware pruner in shadow mode, influxdb3's raised window. Regenerate every module and read every generated `backup.sh` diff. Release in rising order of what a mistake would cost: letsencrypt, zigbee2mqtt, wrangle, homeassistant, mariadb, postgres, plex, influxdb3 | Per module: its pre-install and next nightly runs each write a manifest, no `Prune disagreement`, and secondary's GFS log deletes nothing it did not delete before |
| 4 Restore side | Restore wrapper with chain resolution, `--source`, `replace`/`drill`/`merge`, and every wrapper-held invariant. Each module's staging, sealing and fingerprint hooks. `install.sh` drills after start, as a warning. `fab generate` fails a module defining `restore_merged` without deltas. postgres `restore_applied` rewritten per *Pressure test*, with the extension update after a `replace` (§7). Wholesale replace in `restore_files`, with exclude carry-back and no SQLite sidecars (§8). The per-module `flock` | Per module: its release drill is green. A deliberately corrupted artifact (`--file` pointing at a truncated copy) fails the drill by name, so the drill is shown to bite |
| 5 Recover | influxdb3 `restore_merged`. A drill against the pinned chain, then a bare `merge` run to read the plan, then `--force` | Plan lists every table's days 2026-08-13 → 2026-10-21 and nothing after. The post-restart fingerprint holds every unit. HA's log has no `Catching up, dropped`. Grafana shows the history |
| 6 Release the pin | `backup.sh --full` straight after the merge. Wait for its secondary copy and tertiary snapshot. Then do the incident cleanup in *Cleanup* | That full's fingerprint covers every unit of the staged chain's. Only then delete the post-loss runs and the pin |
| 7 Single pruner (R1) | One Go keep-set in supervisor serving primary, secondary and tertiary, no shadow period (*Decided 2026-11-03*). Drill gating is added in R3, when drills exist to gate on. Supervisor sets `BACKUP_PRUNE=false` when it runs a module script, so no module release is needed | The one-off read-only comparison over every host's run trees and snapshots is clean, the deletion brake bites (a unit test over real directories, and on `jen`'s backlog on 3 Nov), and two consecutive hand-run full backups complete on every host with tertiary |
| 8 Backup engine (R2) | Run lifecycle, manifest, fingerprint, guard and `backup_files` in Go. The generated `backup.sh` becomes the module's snippets plus a shim. Releases all eight modules | Per module: its manifest is byte-identical to the one the bash wrote for the same artifact, its pre-install and next nightly runs succeed, and no pruner is left in any script |
| 9 Restore engine (R3) | Chain, drill, merge, `restore_files` and the per-module lock in Go. Weekly GFS-synced drills (§5a), the `drill` state words, `Fail BKP` reading `drill.json`, and drill gating added to the keep-set. The generated `restore.sh` becomes snippets plus a shim, and `bash/` is deleted | Release drill green per module, the truncated-artifact drill fails by name, a planted failed drill turns `Fail BKP` red, every existing sparse point drilled once. Then run the *Post-R3 review*, fold the durable rules into supervisor's `CLAUDE.md` Backup section, run the residue check, and delete this plan |

### Where this stands and what is next (2026-11-03, updated 2026-11-05)

**Update 5 Nov:** R1 is confirmed by an unattended nightly (item 2.2 below, last paragraph). **R2 is released and verified (5 Nov, below).** The run is `supervisor backup run <module>` (`probe_util_backup_module*.go`, `probe_util_backup_manifest.go`), with hidden `target`, `files`, `parent` and `epoch` verbs that the generated `backup.sh` hooks call back. The generated script is the prelude, the module's hooks and a shim that execs the binary in the container, else `docker exec supervisor`, else `docker run` of the newest installed image. `bash/backup_{hooks,manifest,guard,prune}.sh` and every bash pruner are deleted; `backup_fingerprint.sh` and `asystem_lock.sh` stay until R3 because the restore side still sources them. Checked: six modules' manifests are byte-identical to the bash-written ones from the 5 Nov nightly, and a real generated `backup.sh` ran first run, throttle, regression, `--accept` and `--full` in a Debian container. Each hook now runs in its own `bash`, so no hook may rely on a variable set by another: plex's `backup_completed` reads the container's state instead of a flag. `fab release` commits and tags unless `FAB_SKIP_GIT=1` is set. R3 is next.

**R3 handover, written 5 Nov after R2 for a fresh session.**

*Start by reading* this section, *Decided 2026-11-03*, §4 and §5a, then `probe_util_backup_module*.go` and `probe_util_backup_manifest.go`, which R3 should imitate in shape.

*What exists that R3 builds on.* One manifest reader (`readBackupManifest`) and the typed `backupManifest`; `backupFingerprintUnit`; the run-on-disk helpers in `probe_util_backup_tree.go` (`backupRuns`, `backupRunTime`, `backupRunHolds`, `parentBackupRun`, the `_full` and `_delta` suffix constants); the one keep-set (`backupKeepSet`, `pruneBackupRuns`, `backupKeepPolicy`, `backupKeepRun`) with the brake; `resolveBackupModule`; the per-module `flock` as `moduleLockHeldVariable` plus the lock block in `BackupModuleRun`; hook running as `bash -c '. backup.sh; <hook>'` through `moduleHooks`; the shim in `container.py`'s `BACKUP_WRAPPER` (execs the binary in the container, else `docker exec supervisor`, else `docker run` of the newest `supervisor:*` image), which R3's `restore.sh` shim should reuse as is. The CLI shape is `supervisor backup <verb>` with real cobra flags, the module as a positional argument, `--source` optional (defaults to the module's `latest`, required in practice by `install.sh`, whose new `.env` points `SERVICE_DATA_DIR` at the empty new version), and hidden verbs for the hook callbacks. R3 adds `restore`, `drill` and `merge` the same way, each an exported function in `probe` with the signature `func(context.Context, BackupModuleRequest-shaped request, stdout, stderr io.Writer) int` and an `engine_impl_backup.go` alias, with `cmd_backup.go`'s verb table holding the flags.

*What is left in bash and must go.* `src/all/_/src/build/resources/bash/` still holds `asystem_lock.sh`, `backup_fingerprint.sh`, `restore_chain.sh`, `restore_drill.sh` and `restore_merge.sh`, and `container.py` still templates `RESTORE_WRAPPER` (about 330 lines) and `RESTORE_CONTRACT`. `restore.sh` still sources `backup_fingerprint.sh` (the awk fingerprint), so the Go `fingerprintBackupArtefact` replaces it; the bash and Go fingerprints are unit-for-unit equal on the real archives (checked 5 Nov). The vocabulary parity test (`probe_util_backup_vocabulary_test.go`) reads `restore_chain.sh`, so it goes with that file once no bash mirror remains. The residue check at the end of this plan is the exit gate.

*Rules learned in R2 that R3 must keep.* (1) Each hook runs in its own `bash`, so no hook may rely on a variable set by another: plex's `backup_completed` reads container state for this reason, and restore hooks (`restore_staged`, `restore_sealed`, `restore_teardown`, `restore_merged`, `restore_checked`) must pass state through files the engine owns, as `backup_target` does with its state directory. (2) A drill must run the module's own hooks, so the engine can only call them, never source them into its own process. (3) Single-use helpers are inlined, multi-use helpers local to one function are closures, and tests are table-driven `Test<FileCamel>_<Case>` with expected fields last and no log-text assertions. (4) Order files exported first, unexported helpers and types and constants last. (5) A module release needs the supervisor already released, and `fab release` commits and tags unless `FAB_SKIP_GIT=1` is set.

*R3 scope, from the phase table.* Chain resolution, `--source`, the three modes (`replace`, `drill`, `merge`), `restore_files` with the exclude carry-back and no SQLite sidecars, the per-module lock, the settled-units rule in Go (the module declares open units; the engine never parses `<table>/<YYYY-MM-DD>`), weekly GFS-synced drills in the secondary stage writing `<run>/.meta/secondary/drill.json`, the `drill` state words in `metric_schema.go`, `Fail BKP` reading the newest `drill.json` until a later drill is green, and drill gating in the keep-set (a sparse point counts only once its secondary drill is green). Release order is the same: supervisor, then letsencrypt, zigbee2mqtt, wrangle, homeassistant, mariadb, postgres, plex, influxdb3. Gate: release drill green per module, a truncated artefact fails by name, a planted failed drill turns `Fail BKP` red, and every existing sparse point drilled once.

*Known gaps R3 should close or record.* mariadb has no scratch-container drill; `restore.sh` for the eight modules is still generated from the bash wrapper (R3's whole job); `BackupModuleRun` is a long function of closures by the single-use rule, which is deliberate; there is no unit test of a plex-style hook failing the run because that needs docker.

*Verification habits that worked.* Copy real archives and manifests from the hosts read-only and assert byte-identical output in a Go test gated on `BACKUP_REAL_FIXTURES`; cross-compile the supervisor binary and run a real generated script in a `debian:12-slim` container before any release; read every host's run, manifest, integrity and share `cmp` after a release; use `BACKUP_SKIP_HOURS=0 abackups start` for a fresh nightly-path backup (a plain `abackups start` after a release is throttled by the pre-install backup).

**State on 3 Nov.** The incident is recovered and cleaned up. Phases 0 to 6 are done and released (the progress table below has the evidence). Production holds the full history 2026-08-13 to now. Proven restore points are the fulls `2026-10-29_08-24-14` and `2026-11-02_01-00-38`, and the nightly deltas drill green with the fixed drill (influxdb3 10.200.1926). Nothing is committed by me: the work sits in the working tree for you to stage. Remaining is the Go engine's backup and restore sides (phases 8 and 9, R2 and R3); R1, phase 7, is done.

**Released (28 Oct):** letsencrypt, zigbee2mqtt, wrangle, homeassistant, mariadb 1914, postgres 1908, plex 1909, influxdb3 1913, supervisor 1911. 1913 carries the merge progress lines, the token fix, `backup.sh --full` and the drill fixes; 1914 carries the mariadb drill fix. **Unreleased in the tree:** only the aligned restore log format (a label column and `label  HH:MM:SS  message` progress lines) and the wrapper edits it needed, which ride with the next release of each module, and nothing there is needed for correctness.

**Since then:** influxdb3 10.200.1926 (3 Nov) carries the drill day-boundary fix. The other seven modules' generated `restore.sh` carry it in the tree, unreleased, and pick it up with their next release.

**Remaining, in order**
0. **influxdb3 delta restore: closed 2026-11-03 by decision, without waiting for a recompacting night.** The 29 Oct fault followed the merge recompacting 78 closed windows, so a delta carried replacement run sets beside the full's superseded ones. Settled windows are not recompacted on their own: live's compactor only churns the open window (46 `reason=ReplacedRunSet` deletes, all for `2026-11-03`), so ordinary nightly deltas do not reproduce it. Deltas of 30 Oct to 3 Nov drill green with the fixed drill (*Drill day-boundary defect*), and the full `2026-10-29_08-24-14` and the 2 Nov full are proven restore points. **The standing rule instead:** after any merge, backfill or other write into closed days, force `backup.sh --full` before the next nightly delta. To check whether windows were recompacted, count `grep 'reason=ReplacedRunSet'` by `window=` in `docker logs influxdb3` on `may`, never `compactor.*(plan|publish|dispatch)`, because live's log filter holds `enterprise::compactor` at `warn`. Container logs reset on every release. If a delta ever fails its drill with units short, the rule was missed: take a full and drill it.
1. **Incident cleanup: done 2026-11-03 on `may`.** Deleted from primary the post-loss runs `2026-10-22_08-11-23` and `2026-10-22_08-15-13` and the merge safety backup `2026-10-28_13-54-08`, from the share that safety backup (the post-loss runs were already off the share, and `/tmp/backup` already gone), the pin `/share/30/tmp/influxdb3-restore-2026-10-22/`, and the stale scratch `restore/2026-10-29_01-00-38` and `restore/2026-10-30_01-00-38`. Checked afterwards that none remains and influxdb3 is healthy. Tertiary snapshots still hold the post-loss runs by design. **Not removed, a separate decision:** the post-loss chain `full-2026-10-26` and the early 28 Oct runs up to the post-merge full `2026-10-28_15-02-54`, which *Cleanup* also lists for phase 6, and which GFS and the primary window will age out. Restoring any of them would wipe history, so never restore anything before the 28 Oct 15:02 full.
2. **Next, in order:**
   1. **Scratch-sweep defect: fixed in the tree 2026-11-03, unreleased.** `restore_swept` in `bash/restore_drill.sh` removes every other dir under `<home>/restore/` before staging, called by both drill and merge, and leaves `*.merged` resume files. Covered by a unit test; all eight modules regenerated. It ships with each module's next release.
   2. **R1, single pruner (phase 7), done and released 2026-11-03.**
      - **Built:** `probe_util_backup_keep.go` holds `pruneBackupRuns` (with the brake that refuses a pass deleting more than half a directory's runs), `readKeepRuns` and `backupKeepSet` (window, daily, weekly and monthly tiers, newest, newest full, anchor, parent closure). Table tests in `probe_util_backup_keep_test.go` cover the incident shape, anchor release on `--accept`, the tiers, and the prune and brake boundaries against real directories. Drill gating is not built in R1 and is added in R3.
      - **Wired and released 2026-11-03 (supervisor 10.200.1933).** Primary prunes its run dir after the script exits (window from `retain_days`), with supervisor setting `BACKUP_PRUNE=false` for the script. Secondary prunes the share dir after the rsync in place of the module's `--prune-gfs` and the generic `gfsThin`, which is deleted. Tertiary prunes its snapshots with the same function and the global window. A tripped brake logs ERROR and deletes nothing. Primary and secondary then fail the stage (primary fails that service). Tertiary only logs the ERROR, because its prune runs after the snapshot and a refused prune leaves the snapshots untouched. `config.json` now carries `retain_days` and a per-module `modules` map, which supervisor's `generate.py` fills from each enrolled module's `.env_all`, taking `<MODULE>_BACKUP_NEXT_*` over `<MODULE>_BACKUP_*` over the default, so influxdb3 gets 14 days, weekly 8 and monthly 12 and plex monthly 2. A run counts as a full unless its only artefacts are deltas, so a snapshot or a supervisor run tree is a full. `BACKUP_RETAIN_DAYS_DEFAULT` joins the other defaults in `container.py`, and the generated scripts are byte-identical. The full supervisor and config Go suites and the 124 Python unit tests pass.
      - **Behaviour changes at the release:** (1) influxdb3's primary window widens from 7 to 14 days, so nothing is deleted for a week and its primary grows by about a week of deltas; (2) a directory that would lose more than half its runs in one pass now fails the stage instead of thinning, so shrinking a window by hand needs it done in steps; (3) the pre-install and hand-run backups still prune with the old bash code until R2.
      - **Read-only comparison: done 2026-11-03 for primary and secondary, clean.** Skeletons (run names, artefact names, `.meta` files, no data) of every run tree were copied from `mad`, `meg`, `may` and `max`: 39 directories, primary `/home/asystem/<svc>/backup` and secondary `/share/<index>0/backup/<svc>`. The Go keep-set and the bash `backup_gfs_kept` or window rule ran over the same skeletons with each module's own windows. **No run the old pruner keeps would be deleted**, with the old windows and with influxdb3's wider `NEXT_*` ones, where Go only keeps more (influxdb3's primary keeps all 28 runs against 22, and its secondary keeps `2026-10-04_01-00-50` as well). The brake never trips. Two findings, both fixed in the tree: (1) a delta with no manifest must hang off the run before it, as the old pruner infers (it kept `2026-10-27_01-00-35` that way); (2) tertiary snapshots hold no `_full` artefacts at their top, so `readKeepRuns` treats a run holding no `_delta` artefact as a full, or no weekly or monthly point would ever be kept. **Tertiary compared 2026-11-03, clean:** a hand-run tertiary stage on `may` (shares 30, 31, 32, 17 snapshots each including the new one) pruned nothing under the old `gfsThin`, and the Go keep-set keeps all 17 with the brake clear. **Not compared offline:** `raspbpi-jen`, whose first real run was refused by the brake (below), and `mad`, `meg` and `max` tertiary, which pruned nothing in the real runs.
      - **R1 released and gated 2026-11-03.** Supervisor 10.200.1933 went to every host. Two hand-run full `abackups start` runs (17:04 and 17:49) ended `success` on `mad`, `max`, `may` and `meg` with tertiary, and on `jen` with primary and secondary. No stage failed in the second run, the brake never tripped in it, and the pruner's `expunged` lines show only runs outside the keep set (supervisor run trees, aged `wrangle`, `plex`, `letsencrypt` and `influxdb3` entries, including `influxdb3`'s post-loss runs `2026-10-22` to `2026-10-25` on the share). Tertiary pruned nothing, as the comparison predicted. **The brake bit once, as designed:** the first run's `jen` secondary was refused because `/share/10/backup/supervisor/raspbpi-jen` held 32 runs with 17 outside the keep set. The two oldest doomed runs were deleted by hand to get under half, and the stage then pruned the rest. Any other first-time shrink of a large backlog needs the same stepping. **Failed-drill half moved to R3:** no Go code reads `drill.json` or feeds `Fail BKP` from a drill yet (only the state words exist in `metric_build.go`), so there is nothing to plant a failure against until R3 writes and reads it.
      - **Finding, fixed and released 2026-11-04: secondary re-copied what it then pruned.** The second run pruned the same runs the first had (`mad` 14 supervisor trees, `plex`, `wrangle`, `may` four `influxdb3` runs). Primary still holds them (supervisor's local run trees, and `influxdb3`'s 14-day `NEXT` window against the share's 7 daily), so each night's rsync copied them back to the share and the keep-set deleted them. Harmless while the share stayed under the brake, but the backlog grew past half, and the 4 Nov 01:00 nightly then failed the secondary stage on all five hosts (`prune of [...] refused, [n] of [m] runs fall outside the keep set which is more than half`), so `Fail BKP` read 50%. Nothing was lost: primary passed everywhere. **Fix:** `promoteOneService` computes the keep set over the source directory before the rsync, with the same policy as the post-rsync prune, and passes each run outside it as `--exclude /<run>/`, so the share never regains them. No exclusion when the config declares no retention. No test of its own (it needs a config, a share and a home root); the keep set it calls is table-tested. **One-off cleanup, by hand on the shares, 4 Nov:** the exclusion does not shrink a backlog already there, so the brake still refused after the release. Per directory, only runs the keep set already marks as outside it were deleted, just enough to get under half: `mad` 8, `meg` 8 (`supervisor/macmini-meg`) and 3 (`homeassistant`), `may` 3, `max` 8 (`supervisor/macmini-max`) and 3 (`letsencrypt`), `jen` 6. The supervisor directories took their names from the 3 Nov 17:49 `expunged` lines; `homeassistant` and `letsencrypt` had none, so their set came from running `backupKeepSet` over copies of the run names and manifests (it reproduced the real refusals, 11 of 20 and 14 of 26). The next run's own prune cleared the rest (`mad` 33 to 14, `may` 34 to 17, `jen` 33 to 15). **Verified the same day by hand-run `abackup start` with `BACKUP_SKIP_HOURS=0` on every host (09:11): run `success` with primary, secondary and tertiary `success` (tertiary `skipped` on `raspbpi-jen`) and no `ERROR` or `WARN` in any run log.** **Unattended confirmation, the 5 Nov 01:00 nightly (checked read-only 08:13): passed on all five hosts.** Every run resolved `success` with primary, secondary and tertiary `success` (`skipped` tertiary on `raspbpi-jen`, which has no `/backup`), in 122 s on `mad`, 30 s on `meg`, 179 s on `may`, 19 s on `max` and 15 s on `jen`. Primary reported `0 failed and 0 regressed` everywhere, every `status.json` read `success_bool` true, and no `WARN`, `ERROR`, refused prune or `Prune disagreement` line appeared in any run log. Secondary expunged one aged run (the 29 Oct one) per directory and no backlog, so the exclusion before the rsync holds and the brake never came near tripping. Every module's newest manifest reads `verdict` success (letsencrypt, zigbee2mqtt, wrangle, plex, postgres 153 units, homeassistant, mariadb, influxdb3). influxdb3's delta `2026-11-05_01-00-20` (11M, parent `2026-11-04_08-59-00`, 3425 units, 10.200.1926) is byte-identical on `/share/30/backup/influxdb3/` and passes `gzip -t`. Not checked: the weekly drill (none exists in Go until R3) and drill verdicts. Any other first-time shrink of a large backlog still needs the same stepping.
   3. **R2, backup side (phase 8): done and verified 5 Nov.** **R3, restore side (phase 9): next**, a supervisor release followed by eight module releases in rising cost, gated as in the phase table, *Decided 2026-11-03* and *R3 handover* below.
   4. When R3's gate holds, fold the durable rules into supervisor's `CLAUDE.md` Backup section, run the residue check, delete this plan.
3. **Unscheduled:** UPS and NUT (§6), the InfluxData fsync report, and the known gaps below.

**R2 released and verified, 5 Nov 10:00 to 10:35 (read-only, all five hosts).** Supervisor 10.200.1953 is healthy on `mad`, `meg`, `may`, `max` and `jen`, then the modules in rising cost: letsencrypt (pre-install run 09:58), zigbee2mqtt 1955 (10:04), wrangle 1956 (10:09), mariadb 1957 (10:14), homeassistant (10:18), postgres 1960 (10:24), influxdb3 1962 (10:29) and plex 1963 (10:31). influxdb3 was not upgraded, only re-released on 10.200.1926 data. Every module's pre-install run went through the new shim and engine and wrote a manifest with `verdict` success, and every release drill recorded `success` in `.meta/primary/drill.json` (letsencrypt, zigbee2mqtt, wrangle, mariadb, homeassistant, postgres, influxdb3, plex), with no scratch container or `restore/` directory left behind. The influxdb3 pre-install delta `2026-11-05_10-29-00` has `parent` `2026-11-05_01-00-20` and 3466 units. postgres printed `database "hass" does not exist, skipping` notices from its drill, which are `DROP DATABASE IF EXISTS` against the empty scratch server; the live `hass`, `mlflow`, `wrangle` and `postgres` databases were present and healthy. The notices are silenced by `client_min_messages=warning` on the two `DROP ... IF EXISTS` calls in `postgres_restore_loaded`, released in postgres 10.200.1960 (the installed `restore.sh` carries it, and its pre-install run `2026-11-05_10-24-44` drilled `success`). The only ERROR lines in the supervisor logs over the release hour were memory-sampling probe faults for short-lived `*_bootstrap` and `*_restore` containers, not backup faults. **Hand-run `abackups start` at 10:35, all five hosts:** run `success` on every host with primary, secondary and tertiary `success` (tertiary `skipped` on `raspbpi-jen`, which has no `/backup`), 0 failed and 0 regressed, no `WARN`, `ERROR`, refused prune or `Manifest could not be written` in any `run.log`, in 76 s on `mad`, 35 s on `meg`, 50 s on `may`, 21 s on `max` and 2 s on `jen`. **Every module read `skipped`**, because the pre-install backup taken minutes earlier was inside the one-hour throttle (`skipping given within [1] hours`), so this run proved the stage pipeline over the new engine's runs and the skip path, not a fresh engine backup. The newest run of each module is its pre-install one: every manifest `verdict` success with the 01:00 nightly as `baseline`, every archive passes `gzip -t` or `unzip -t`, and every archive is byte-identical on its share (`plex`, `postgres`, `wrangle`, `homeassistant`, `mariadb`, `influxdb3`, `letsencrypt`, `zigbee2mqtt`). A fresh engine backup of each module from the nightly path still needs `BACKUP_SKIP_HOURS=0 abackups start` or the 6 Nov nightly. **Fresh engine backup, `BACKUP_SKIP_HOURS=0 abackups start` at 10:40, all five hosts: passed.** Every host's run resolved `success` (77 s on `mad`, 35 s on `meg`, 49 s on `may`, 22 s on `max`, 16 s on `jen`) with primary, secondary and tertiary `success` (tertiary `skipped` on `jen`), 0 failed and 0 regressed, no `WARN`, `ERROR`, refused prune or `Manifest could not be written`. All eight modules wrote a new run through the nightly path, none `skipped`: plex 516 MB, postgres 49 MB (159 units), wrangle 6 MB, mariadb 2 MB, homeassistant, letsencrypt, zigbee2mqtt (8 entries) and influxdb3 a delta of 11 MB with `parent` `2026-11-05_10-29-00` and 3466 units. Every manifest is `verdict` success with no evidence and its previous run as `baseline`, every archive passes `gzip -t` or `unzip -t`, and every archive is byte-identical on its share. No scratch container or `restore/` directory was left. **influxdb3 delta rule, written 5 Nov, unreleased.** `backup_written` now takes a full instead of a delta unless the server-side full it would hang off was written by the same `source_version`, read with `jq` from that run's `.meta/manifest.json` (a missing or unreadable manifest also forces a full). The first backup after any influxdb3 release, including a product upgrade, is therefore a full of about 200 MB and every later delta hangs off it, which removes the unproven case of a delta written by a new version on a full written by an old one. The pre-install backup is unaffected: its source is still the old version directory, so it stays a delta and the rollback chain is kept. It is module-specific, so it lives in the snippet and not in `install.sh`, where a generic forced full would cost every module release. Covered by `src/may/influxdb3/src/test/python/unit/unit_test.py`, which runs the generated hook against stub `docker` and `supervisor` commands (same version, other version, missing manifest, earlier ISO week, `--full`); removing the version check fails the first two. **Released as influxdb3 10.200.1965 (5 Nov 10:52), server unchanged at 3.12.1, and verified.** Container healthy; the installed `backup.sh` carries the rule. Its pre-install backup `2026-11-05_10-52-51` was a **full** (`kind` full, `src` 10.200.1962, 3466 units, `verdict` success, `baseline` `2026-11-05_10-40-32`), not a delta, and its release drill recorded `success`. That is the rule working on its first run, not a fault: the week's full had been written by 10.200.1926 and the running version was 1962, so nothing could parent a delta. It also left the server-side store holding only `full-2026-11-05_10-52-51`, as the existing prune intends. **Correction to the statement above:** the pre-install backup stays a delta only in steady state, when the last full was written by the version being replaced; this first release after the rule is the one-off exception. The first backup after 1965 (the next nightly) will be a full again, written by 1965, and from the release after that the pre-install backup is a delta. The only influxdb3 log errors in the release window were four `hyper::Error(IncompleteMessage)` lines at startup from clients dropping connections during the restart. The new full is on primary only; its secondary copy and tertiary snapshot arrive with the next run of those stages. **The product upgrade is now unblocked once the 6 Nov nightly is clean.** (Originally: needs an influxdb3 release before or with the upgrade.) The upgrade order: nightly of 6 Nov clean, then release influxdb3 with this rule on the current version, then upgrade as its own release, then drill the resulting full by hand (`restore.sh --mode=drill --from=<run>`) until R3's weekly drills do it. **Still open:** the first unattended nightly after R2 (6 Nov 01:00): check every host's run, each module's new manifest, secondary and tertiary, and that no `Manifest could not be written` or refused-prune line appears.

**Known gaps, not blocking:** mariadb has no scratch-container drill, so its restore is proven by artifact only; a postgres dump taken before the extension update cannot be loaded on the current image; dependents are not stopped during a replace; tertiary is reached only through `--source`; the per-module `flock` is untested because the build machine has no `flock`. The influxdb3 admin token was exposed in `ps` and in the conversation during the merge; the script no longer puts it on a command line, and it was decided on 2026-10-28 not to rotate it.

**Facts that are not obvious from the code**
- Hosts: ssh as `root@macmini-{mad,meg,may,max}` and `root@raspbpi-jen`. `jil` does not resolve and is out of scope.
- `abackups start` now forwards `BACKUP_SKIP_HOURS` to each host (numeric only, else exit 2). The 09:42 run on 28 Oct confirmed it: no service was throttled. The dispatcher ran from `rue`, a client host, and each supervisor release installs its own copy of `backups.sh` there. So the change reaches a dispatching host with a supervisor release. Where a copy predates it, `ssh root@<host> 'BACKUP_SKIP_HOURS=0 abackup start'` does the same. No other `BACKUP_*` variable should be forwarded: `BACKUP_SERVICE_RESTART` is set by supervisor itself and `BACKUP_HOME_ROOT` is a test override.
- A hand-run `abackup start --stage primary|secondary` writes a run with no tertiary document, which blanks `Used BKP` until the next full run. Set `BACKUP_SKIP_HOURS=0` to defeat the throttle. A fresh release is `health: starting` for a while and primary refuses it.
- Plex stops for about 22 s whenever its backup runs, whether by hand or by stage.
- An entrypoint drill must set `INFLUXDB3_DATA_DIR=/asystem/mnt`, because the image defaults to another path.
- Restoring a delta replaces the source's whole state, so never restore anything before the 28 Oct 15:02 full. The 22 Oct post-loss runs are deleted, but the 26 Oct post-loss chain is still on primary and the share until it ages out.
- The pin `/share/30/tmp/influxdb3-restore-2026-10-22/` was deleted on 3 Nov. The history is in live and in fulls on primary, the share and tertiary.
- Each postgres release costs HA about 70 s of recorded states.
- The hand rules from CLAUDE.md apply: read-only git, no edits to `resources/metadata/entity_metadata.xlsx`, `shellcheck` on every script, `[$VAR]` log messages.

### Release windows

Phases are written and gated one by one, but released in three windows. A window ends at its gate, and nothing in the next starts before it holds.

| Window | Phases | Order inside | Gate before the next window |
|---|---|---|---|
| A | 1, 1b, 1c | `fstab` remount on each host (no release); homeassistant leftovers and stale `.storage` copies deleted on meg; every module whose generated `backup.sh` or `restore.sh` changed (plex, letsencrypt, wrangle, others after reading the diffs); homeassistant; postgres; influxdb3 | `findmnt -no OPTIONS` shows no `commit=600`; every database at `extversion = default_version`; each released module's next nightly run succeeds; homeassistant shows in primary and secondary; the influxdb3 scratch drill refuses on zero-length checkpoints |
| B | 2, 3 | supervisor to every host first, then modules in rising cost: letsencrypt, zigbee2mqtt, wrangle, homeassistant, mariadb, postgres, plex, influxdb3 | phase 2 gate on every host; then per module a manifest on its pre-install and next nightly run, no `Prune disagreement` |
| C | 4, then 5 and 6 as runs, then 7, 8 and 9 | each module's release drill; the merge is a production run, not a release | release drill green per module and the truncated-artifact drill fails by name; phase 5 and 6 gates; phases 7 to 9 are the three releases R1 to R3 (*Decided 2026-11-03*), each gated on its own comparison and nightly runs |

#### Window A progress, 2026-10-28

| Step | State |
|---|---|
| `commit=600` removed from the `fstab` sources and `/etc/fstab`, hosts rebooted | `may`, `meg`, `max` confirmed with no `commit=` on `/`, `/home`, `/var`, `/tmp`. `jil` is out of scope for this gate by decision 2026-10-28: its `fstab` source is edited but its mounts are not checked here |
| Code for phases 1, 1b, 1c (entrypoint quarantine-and-refuse, health floor, postgres bootstrap, `backup_files` tar retry, wholesale `restore_files`, homeassistant enrolment) | Written, `fab generate` passes for all eight enrolled modules, not yet released except as below |
| homeassistant leftovers and the two stale `.storage` copies on meg | Deleted |
| letsencrypt 10.200.1878, zigbee2mqtt 10.200.1879, wrangle 10.200.1881, mariadb 10.200.1882, plex 10.200.1883 | Released, containers healthy, each took its pre-install backup |
| Manual `backup.sh` run of those five (`BACKUP_SKIP_HOURS=0`, 09:07 to 09:08) | Passed. All five exited 0 with no "Not backed up and not excluded" line and a clean archive test. letsencrypt 1 MB, zigbee2mqtt 8 entries, wrangle 79 entries and 7 MB, mariadb 3 MB with 4 databases, plex 516 MB with no `-wal` or `-shm` in the archive. plex restarted healthy in about 26 s, and a bare `restore.sh` printed its plan (stopped, extract the config, integrity passed) with nothing changed |
| Supervisor stages (primary, secondary, tertiary) succeed for those five | Passed by a full manual `abackup start` at 09:42 on 28 Oct, which runs the same stages as the nightly. The scheduled trigger was not separately waited for: leader election is healthy after the restart and nightly runs have followed every earlier release |
| homeassistant 10.200.1884 then 10.200.1885 released | Passed on 10.200.1885. The first release's manual backup reported `Not backed up and not excluded [bootstrap.sh healthcheck.sh]`, so both were added to the excludes. On 10.200.1885 the manual backup exited 0 with no unmatched line. The archive passes `gzip -t` with 105 `.storage`, 11 `blueprints` and 2 `custom_templates` entries, and has no `tmp*`, `*.bak-*` or `*.migration_backup`. A bare `restore.sh` names exactly `.storage:blueprints:custom_templates`. HA is healthy after startup |
| Supervisor stages on meg, run by hand 09:14 (`abackup start --stage primary`, then `--stage secondary`) | Passed. A first primary run failed by design: homeassistant was still `health: starting` and primary refuses a container that is not healthy yet. The rerun with `BACKUP_SKIP_HOURS=0` ended `success` for homeassistant and mariadb, and secondary promoted both to `/share/40/backup/`, where the homeassistant archive passes `gzip -t`. Secondary also thinned old supervisor runs with the generic pruner, as it always does for a module with no `backup.sh`. Tertiary was not run, and it needs the backup disk powered on |
| postgres 10.200.1886 released (own release) | Passed. All five databases (`hass`, `mlflow`, `postgres`, `template1`, `wrangle`) report `extversion = default_version = 2.30.2`. The generated `image/bootstrap.sh` holds the banner once. Container healthy |
| Postgres cost, observed | HA's recorder logged `Database connection invalidated` and a `PendingRollbackError` at 09:16, then recovered unaided. `hass.states` has a gap from 09:15:10 to 09:16:22, about 72 s, matching the release restart, and it is recorded at 1 s resolution after. The loss is the restart, not the extension update alone, and no `Catching up, dropped` line was logged. Accept for each postgres release |
| Backups on mad by hand 09:17 (`abackup start --stage primary` then `--stage secondary`, `BACKUP_SKIP_HOURS=0`) | Passed. plex (22 s), postgres (7 s) and wrangle (1 s) all `success`, then secondary promoted plex, postgres, wrangle and supervisor to `/share/10/backup/`. The postgres dump passes `gzip -t` locally and on the share, holds 147 `COPY` lines, and has `CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public` (no pinned version). plex came back healthy 23 s after |
| `Used BKP` blank on mad and meg after the hand-run stages | Expected, not a fault. `usedBackupSpace` reads the newest run's tertiary document, and a `--stage primary` or `--stage secondary` run has none, so the metric errors with `no tertiary stage document`. It clears at the next nightly run, or after a hand-run `--stage tertiary`, which powers the backup disk. Hand-run stages should include tertiary, or be followed by one, when the display matters |
| influxdb3 10.200.1887 released | Passed. Container healthy on the new image. `/tmp/influxdb3_floor` exists inside it and reads `1792627765927698000` ns, the post-loss floor (22 Oct), so the check only fires if the floor moves **later** and the merge in phase 5 will move it earlier, which is allowed. The entrypoint logged nothing and made no quarantine dir on a clean start. `old home 10.200.1850` is gone and `10.200.1851` remains |
| Entrypoint scratch drill (throwaway containers on may, no network, image `influxdb3:10.200.1887`, stock entrypoint stubbed) | Passed on all three cases. All checkpoints empty: both moved to `cv2/quarantine/<ts>/`, "refusing to start" printed, exit 1, nothing deleted. One empty and one good: the empty one quarantined, the good one kept, hand-off to the stock entrypoint. No checkpoints (fresh install): straight hand-off. A first attempt used the image's default `INFLUXDB3_DATA_DIR`, not the module's `/asystem/mnt`, and so tested nothing, so a drill must set it |
| Backups on may by hand 09:22 (`abackup start --stage primary` then `--stage secondary`) | Passed. A `delta` of version 10.200.1887 was written (1 s) and promoted to `/share/30/backup/influxdb3/`, where it passes `gzip -t`. The incident chain `2026-10-19_01-00-28` to `2026-10-22_01-00-08`, the two post-loss captures and the pin `/share/30/tmp/influxdb3-restore-2026-10-22/` (five runs) are all untouched |
| supervisor 10.200.1888 released (about 09:36 to 09:40) | Passed. Container `healthy` on `max`, `meg`, `mad`, `may` and `raspbpi-jen` at 09:50, and it carries the `abackups` change forwarding `BACKUP_SKIP_HOURS`. A hand-run full `BACKUP_SKIP_HOURS=0 abackups start` from `rue` at 09:42 followed it: all five hosts `success` with tertiary `success` (`skipped` on `raspbpi-jen`), every service exported rather than throttled, no `WARN` or `ERROR` in any `run.log`, `Used BKP` restored. `meg`'s earlier `failure` at 09:14:23 was primary refusing `homeassistant` while it was `health: starting` just after its release, not a fault. It left that service no `status.json`, which phase 2 now covers |
| supervisor 10.200.1889 released (phase 2, `regressed` only) | Passed. Container `healthy` on all five hosts. A full `BACKUP_SKIP_HOURS=0 abackups start` at 10:26 followed it: every service `success` on primary, secondary and tertiary (`skipped` on `raspbpi-jen`), no `WARN` or `ERROR` in any `run.log` or supervisor log, `Used BKP` populated. Nothing emits `regressed` yet, so the planted-run test is still to do |
| Phase 2 gate, first attempt (28 Oct 11:26, `max` `letsencrypt`, supervisor 10.200.1898) | **Failed one item, fix written.** Planted by inflating `letsencrypt/archive` in the previous manifest from 71002 to 7100200, so the real guard fired on a full `BACKUP_SKIP_HOURS=0 abackup start`. Passed: the new run's manifest read `regressed` with its evidence, the log and tail read `faulting regressed [0] closed units missing against [2026-10-28_10-52-55], total [-98]% beyond [20]%`, the stage and the run read failure, the exit code was non-zero, and the archive was kept. **Failed:** secondary and tertiary never ran, so the regressed run did not reach the share. Cause: the run loop halts on any stage error, so a regressed primary stopped the rest, against §2. Fix: a regressed primary now returns `errStageRegressed`, which fails the stage and the run but lets the later stages run (`runStageSequence`, table-tested, a hard failure still halts). Cleanup done by the real paths: the manifest restored byte for byte, `backup.sh --accept=2026-10-28_11-26-57` flipped the regressed run to `success` with `accepted` true, and a clean full run followed whose `baseline` named the accepted run. **To redo after the fix is released:** the same plant, then check the run reaches `/share/10/backup/letsencrypt/` and tertiary, `abackup tail` shows `as [regressed]`, `BKP` reads false and `Fail BKP` non-zero, a following throttled run reads `skipped` without re-reporting it, and two consecutive nightly runs complete with tertiary. Not exercised: the failed-drill half, which waits for phase 4 |
| Phase 2 gate, second attempt (28 Oct 11:45, `max` `letsencrypt`, supervisor 10.200.1899) | **Partly passed, one more fix.** Passed: secondary and tertiary ran, so the regressed run reached `/share/*/backup/letsencrypt/`; the stages read primary `failure`, secondary and tertiary `success`; the run read `failure` with `stages_failed` 1 of 3, so `Fail BKP` reads 33%; the log read `as [regressed]` with its evidence, `[1] services attempted with [0] failed and [1] regressed`, and the exit code was non-zero; the service document carried `state` `regressed` and `success_bool` true. **Failed:** the service document had no `regressed_bool`, so `BKP` could not read false. Cause: an edit that added `RegressedBool` to the document literal in `runOneService` never applied, because the replacement was not checked. Fixed, with the doubled error wording tidied. The writer has no unit test (it needs docker), so the gate is what guards it. Cleaned up by the real paths as before. **To redo after the fix is released:** plant again and check the service document carries `regressed_bool` true and `BKP` reads false, then a throttled run reads `skipped` without re-reporting it, and two consecutive nightly runs complete with tertiary |
| Phase 2 gate, third attempt (28 Oct 11:58, `max` `letsencrypt`, supervisor 10.200.1901) | **Passed, apart from the two consecutive nightly runs.** Planted as before. The run reached `/share/20/backup/letsencrypt/`; the stages read primary `failure`, secondary and tertiary `success`; the service document carried `state` `regressed`, `success_bool` true and `regressed_bool` true; the log read `as [regressed]` with its evidence line and `[1] services attempted with [0] failed and [1] regressed`; the exit code was non-zero. Seen on the dashboards: `Fail BKP` red at 33% on `max`, and `BKP` for `letsencrypt` red (false). The next plain `abackup start`, throttled, read `skipped` for `letsencrypt`, reported `[0] regressed`, and the whole run read `success`, so a regression is not re-reported by a skipped run and the red clears with it. Cleaned up by the real paths: the manifest restored byte for byte and `backup.sh --accept=2026-10-28_11-58-22`. **Two consecutive runs, done by hand rather than waiting for the nightly:** two full `BACKUP_SKIP_HOURS=0 abackups start` runs (12:02 and 12:04 on 28 Oct) completed on all five hosts with primary, secondary and tertiary `success` (`skipped` tertiary on `raspbpi-jen`). **Still open:** the failed-drill half, which waits for phase 4 |
| Phase 3 and 4 batch release (28 Oct 13:12 to 13:30, supervisor 10.200.1911) | **Passed, one defect found and fixed.** All nine releases went out with tests skipped: letsencrypt, zigbee2mqtt, wrangle 1905, homeassistant, mariadb 1907, postgres 1908, plex 1909, influxdb3 1910 and supervisor 1911. Read-only on every host afterwards: every container `healthy`; every module's pre-install manifest `verdict` `success` naming the preceding run as `baseline`; influxdb3's new manifest names the previous run (`2026-10-28_12-04-22`) as `parent`, not the full; no `Prune disagreement` or `Manifest could not be written` in any supervisor log; a release drill recorded `success` in the pre-install run's `.meta/primary/drill.json` for letsencrypt, zigbee2mqtt, wrangle, postgres, plex, homeassistant and influxdb3; and a deliberately truncated copy of a letsencrypt artifact passed to `restore.sh --mode=drill --file=` failed by name, `the artifact failed its integrity check`, with exit 1. **Defect:** mariadb's release drill recorded `failure` with detail `scratch short`. A SQL dump with no module staging extracts nothing, so scratch was an empty directory and the drill demanded the manifest's units of it, which could never pass. The backup itself was fine and its artifact fingerprint passed first. Fixed in the wrapper, so scratch is compared only when an artifact actually extracts, with two new tests (a passing SQL dump and one holding less than its manifest), and **needed a mariadb release** to take effect (released as 1914, its drill now reads `success`). mariadb therefore has no real restore proof yet beyond the 27 Oct manual load, and its scratch container is still unwritten |
| Merge progress output (28 Oct, written while the first production merge was running, released in influxdb3 1913) | `restore.sh` printed nothing between the plan and the end of a merge. It now stamps a line at each pause: staging each artifact, fingerprinting scratch and live, sealing, the start of the merge, every 30 s while merging (`RESTORE_PROGRESS_SECONDS`) with units done and a percentage, rows, GiB written, MiB/s, units a minute, minutes elapsed, an ETA and the host load, then the restart, each verification attempt with how many units are still short, and the final verified line. The figures come from a stats file each finished unit appends its rows and bytes to, so concurrent workers need no shared variable. Covered by a test. **Released in influxdb3 1913**; the first production merge used the script installed before it, which is why it ran silently, and nothing was copied to the host. The 1913 output predates the aligned format below |
| Admin token visible in `ps` during the production merge (28 Oct 14:05, fixed in influxdb3 1913) | **Defect, found from a pasted `ps` line.** `restore_merged` passed the write token on `curl`'s command line, so the influxdb3 admin token showed in the process list on `may` for the whole merge and in the pasted output. The rehearsal never showed it because its stand-in ran without auth. Fixed: the header now comes from a mode 600 file inside the merge's temp directory, read with `curl --header @file`, and removed with the directory. Checked against a local server that the header still arrives and the token is not in the arguments. **Released in influxdb3 1913. The token that was exposed is the live admin token** (`INFLUXDB3_TOKEN_ADMIN`): it was readable by anyone able to run `ps` on `may` during the merge and it is in the conversation transcript. **Decided 2026-10-28: not rotated.** Rotating would mean updating Home Assistant, grafana and the other writers, and the exposure was limited to root on a single-user host plus the conversation |
| Phase 5 recovery, applied to production (28 Oct, merge finished 14:20, influxdb3 10.200.1910) | **Passed.** `restore.sh --mode=merge --force --from=2026-10-22_01-00-08 --source=/share/30/tmp/influxdb3-restore-2026-10-22` with `RESTORE_MERGE_JOBS=3`, run by hand on `may` and detached. All 2883 planned units merged at about 100 units a minute, live restarted, the script's own verification passed (its progress file, scratch directory and scratch container were all removed, which only happens on success). Checked read-only afterwards on live: `sensor__temperature` holds **4 907 096 rows before 22 Oct, identical to the backup**, the first row is 2026-08-13T02:03Z and the last is current, 77 distinct days (70 restored plus 22 to 28 Oct), 44 tables, and the 520 224 rows live had written since the loss are intact. Home Assistant stayed healthy with **0** `Catching up, dropped` lines in 30 minutes, and supervisor logged no errors. Peak load on `may` was about 6 on four cores, with `influxdb3` itself `healthy` throughout. **Still open for phase 6:** a fresh full backup that covers every restored unit (`backup.sh --full` does not exist yet, see below), then the cleanup, then the pin. **Grafana confirmed by the owner on 28 Oct: the history shows continuously.** |
| `backup.sh --full` (28 Oct, released in influxdb3 1913) | Phase 6 needs a full straight after the merge, and the ISO-week rule would have kept this week on deltas. `backup.sh --full` now sets `BACKUP_FORCE_FULL=true` and skips the throttle, in the shared wrapper, so every module accepts it and only influxdb3 acts on it (the others always take a full). influxdb3 takes a full when asked even where a delta is eligible, and says so in its output. Covered by a test that generates a throwaway module and runs it with and without the flag; the influxdb3 decision itself needs docker, so it is read from the generated script and proven by the first run. **Released in influxdb3 1913.** **Phase 6 sequence:** release influxdb3, run `bash /var/lib/asystem/install/influxdb3/latest/backup.sh --full` on `may`, wait for its secondary copy and tertiary snapshot (the next `abackups start` on that host does both), confirm the new manifest's fingerprint holds every restored unit, and only then delete the post-loss runs `2026-10-22_08-11-23` and `2026-10-22_08-15-13`, the merge's safety backup `2026-10-28_13-54-08` and the pin `/share/30/tmp/influxdb3-restore-2026-10-22/` |
| influxdb3 10.200.1912 release drill (28 Oct 14:33) | **Failed as a warning, two defects found and fixed, drill then passed on `may`.** The release itself succeeded and the failed drill did not stop it, as designed. (1) `restore_staged` is called as `scratch="$(restore_staged)"`, and the progress lines added that afternoon printed to stdout, so they were captured into the scratch address and the fingerprint ran against a multi-line string (`Error response from daemon: page not found`). The merge calls it the same way, so it would have broken too. Status lines now go to stderr, with a test that a captured address stays clean. (2) The `manifest parent … differs from the preceding run` notice printed once per run in the chain on every drill, because every manifest written on 28 Oct names the full as its parent. It is now silent unless `RESTORE_VERBOSE=true`. Re-run on `may` with the fixed script against the same pre-install run (a delta taken after the merge): chain of 13 artifacts, **all 3136 manifest units held**, scratch sealed read only, exit 0, no leftover container or directory. That is the first proof that the restored history restores from a real backup. The real `restore_merged` was also run on a throwaway stand-in with a token to check its output: 0 bytes on stdout and stderr, so the merge itself prints no blank lines. **Needs a further influxdb3 release** to carry both fixes |
| Shell library layout (28 Oct, unreleased) | The wrapper's shared bash now lives in `src/all/_/src/build/resources/bash/`, one file per function prefix: `asystem_lock.sh`; `backup_fingerprint.sh` (the parser shared with restore), `backup_hooks.sh` (the module-overridable defaults `backup_fingerprinted` and `backup_durable`, kept out of `restore.sh` because its drill treats a defined `backup_fingerprinted` as a module hook), `backup_manifest.sh`, `backup_guard.sh`, `backup_prune.sh`; `restore_chain.sh`, `restore_drill.sh`, `restore_merge.sh`. `entity_metadata.xlsx` moved to `resources/metadata/`, content byte-identical. `container.py` concatenates them and drops each file's own `# shellcheck` header. Verified by regenerating all eight modules: 621 functions across 16 scripts have identical bodies before and after, and the only other differences are the dropped directives and a corrected `restore.sh` header comment. The vocabulary parity test now reads `backup_guard.sh` and `restore_chain.sh` |
| influxdb3 10.200.1913 release drill (28 Oct 14:56) | **Passed.** The release drill ran after start against the pre-install run `2026-10-28_14-54-53` (a delta taken after the merge): chain of 14 artifacts, all 3136 manifest units held, scratch sealed read only, exit 0, and the release completed. This carries the corrected stdout capture, the silent manifest-parent notice, the token-off-the-command-line fix and `backup.sh --full`. The 1913 output predates the aligned log format, which is built and unreleased: every known label (`artifact`, `taken`, `drill`, `staging`, `counting`, `sealing`, `merge`, `verify`, `short`, `backup`, `extracted` and so on) sits in one 10-wide column through `restore_report`, free-text notes sit under the detail column, and progress lines read `label  HH:MM:SS  message`. It ships with the next module release |
| Phase 6, post-merge full backup (28 Oct 15:02, influxdb3 10.200.1913) | **Passed.** `backup.sh --full` on `may` wrote run `2026-10-28_15-02-54`: a 202 MB `_full.tar.gz` that passes `gzip -t`, manifest `kind` full, `parent` empty, `verdict` success against `baseline` `2026-10-28_14-54-53`, no evidence, **3136 units across 44 tables and 77 days (2025-10-13 stray, then 2026-08-13 to 2026-10-27)**, and `sensor__temperature` holding 4 907 096 rows before 22 Oct, the restored history exactly. The server-side store now holds only `full-2026-10-28_15-02-54`, as the existing prune intends. A release drill of that full alone, with no chain, staged it into scratch and held all 3136 units, sealed read only, in 28 s, recorded as `success` in its `.meta/primary/drill.json`, with nothing left behind. So one archive now covers the whole recovered history. **Then a plain `abackup start` on `may` (15:17):** primary, secondary and tertiary all `success`, `influxdb3` read `skipped` by the throttle as intended, no `WARN` or `ERROR` in the run log. The share copy `/share/30/backup/influxdb3/2026-10-28_15-02-54/` is byte-identical to primary and passes `gzip -t`, and its `.meta` (the manifest and the primary drill verdict) travelled with it. The pinned incident chain is untouched, 5 runs. **Still to do:** the cleanup deletes below, on explicit go-ahead |
| mariadb 10.200.1914 release (28 Oct 15:54) | **Passed, the open drill failure is closed.** The pre-install run `2026-10-28_15-54-32` has `verdict` success, `baseline` the previous run, 2 units (`mysql`, `weewx`), and its release drill recorded **`success`** in `.meta/primary/drill.json`, where 1907's recorded `failure` (`scratch short`). The container is `healthy`, and there is no `Prune disagreement` or `Manifest could not be written` in supervisor's log. mariadb's drill proves the dump and its per-database bytes; a real restore into a scratch container is still unwritten |
| First nightly run after the batch (29 Oct 01:00, all hosts) | **Passed, one defect found.** Every host's run read `success` with primary, secondary and tertiary `success` (tertiary `skipped` on `raspbpi-jen`, scrub `skipped`), no `WARN`, `ERROR`, `Prune disagreement` or `Manifest could not be written` in any supervisor log since 00:55, all supervisors `healthy` after 18 h. Every module's newest manifest reads `verdict` success: letsencrypt, plex, postgres, wrangle, homeassistant, mariadb, zigbee2mqtt full, and influxdb3 `delta` with `parent` `2026-10-28_15-02-54` and `baseline` the same, 3136 units. The influxdb3 delta (195 MB, gzip clean) is byte-identical on `/share/30/backup/influxdb3/`. **Defect:** a drill of that chain (`restore.sh --mode=drill` on `may`, 08:01) failed with `scratch holds less than the manifest says`, **512 of 3136 units short, each holding 0 rows** (most of 2026-10-07 to 2026-10-21 across the tables, plus a few August and September days). The full alone drilled green at 15:02 on 28 Oct, and the delta chain drilled green at 14:56. What changed overnight: the delta holds 3311 windows against the full's 821 and 2966 files, because PachaTree recompacted the restored windows. For 2026-10-14 the full has one run set (`...44`, one file) and the delta a replacement run set (`...45`, 39 files). So either the engine's incremental restore does not honour a replaced run set, or the wrapper's staging of a delta over a full does not. **Diagnosed 29 Oct, to the engine.** `restore_staged` only extracts each archive under `backups/<full>/` or `.../incremental/` and calls the engine's own `influxdb3 create restore --backup <name>`, so the wrapper does nothing to a delta that the engine does not. A drill kept with `--keep-scratch` showed the scratch server's compactor logging 31 `refusing compaction publish with invalid L2 ranges ... TimeDisjointTwoLevel l2 assigned ranges overlap` errors, one per window from 2026-09-01 on. Live logs none. So the engine restores the delta's replacement run set beside the full's superseded one, and the overlap leaves those units unreadable. The cause is the one-off recompaction of every window the merge touched (78 windows in one delta), which a fresh full as the parent should clear. **Unproven:** that a delta of already settled windows restores, which only tomorrow's drill against a new full shows. Until then, only `full-2026-10-28_15-02-54` is a proven restore point, and every nightly delta on this chain is suspect. The drill left no scratch container and an empty `restore/` directory |
| Recovery from the delta defect, by hand on `may` (29 Oct 08:24 to 08:27, run by the owner) | **Partly done.** The compactor was quiet first: no plan, publish or dispatch lines in 30 minutes of `influxdb3` logs, only retention deletes on today's window. A `backup.sh --full` wrote `2026-10-29_08-24-14` (205 MB in 26 s, manifest `success`, `kind` full, 3180 units, 44 more than the 15:02 full, one extra day per table). Its release-style drill alone **passed**: chain of 1, every unit held, scratch sealed read only, and it removed the scratch container my kept-scratch drill had left. A `BACKUP_SKIP_HOURS=0 backup.sh` delta straight after (`2026-10-29_08-26-51`) took under a second, parent the new full, `success`, 3180 units, **236 KB** against the failed delta's 195 MB. Three `Prune disagreement` lines appeared on both runs (`2026-10-22_01-00-08`, `2026-10-22_08-11-23`, `2026-10-22_08-15-13`), all in the harmless direction: the old pruner would delete them as older than 7 days and the new one keeps them. **Then, by me at 08:29 to 08:31:** the chain drill of that delta **passed** (chain of 2, all 3180 units held, scratch sealed read only, no scratch container left). The server store holds only `full-2026-10-29_08-24-14`, so the 15:02 full is gone from it and survives on primary, the share and tertiary. A full `BACKUP_SKIP_HOURS=0 abackup start` on `may` (run `2026-10-29_08-29-52`) read `success` on primary, secondary and tertiary, both new runs are byte-identical on `/share/30/backup/influxdb3/` and pass `gzip -t`, and tertiary snapshotted `share/30` at `2026-10-29_08-29-52`. Over the previous two hours live logged no `refusing compaction publish`, the compactor was quiet, and Home Assistant on `meg` logged no `Catching up, dropped`. **Still open:** a repeat of delta and drill a few hours later as the stand-in for the overnight gap, and tomorrow's 01:00 delta, which is the real confirmation. A delta taken minutes after a full has nothing to rewrite, so passing it proves only that the path works |
| Test B, second nightly run (30 Oct 01:00, all hosts; drilled 08:20 on `may`) | **Passed, with the compactor idle.** Every host's run read `success` and no supervisor log held `WARN`, `ERROR`, `Prune disagreement` or `Manifest could not be written`. Every module's newest manifest reads `verdict` success (letsencrypt, plex, postgres, wrangle, homeassistant, mariadb, zigbee2mqtt, influxdb3). The influxdb3 delta `2026-10-30_01-00-38` has `parent` `2026-10-29_08-29-52`, is **5.1 MB** (against the failed delta's 195 MB), and is byte-identical on `/share/30/backup/influxdb3/` and passes `gzip -t`. `restore.sh --mode=drill --keep-scratch` restored a chain of 4 (the 08:24 full and three deltas): all 3180 manifest units held, scratch sealed read only, exit 0, and the scratch log held 0 `refusing compaction publish` lines. **Caveat:** live logged 0 compactor plan, publish or dispatch lines since 29 Oct 00:24Z and 0 `refusing compaction publish`, so there was nothing to rewrite and this shows the path works rather than that recompaction is harmless. The scratch container was removed by hand; the dirs `restore/2026-10-29_01-00-38` and `restore/2026-10-30_01-00-38` were left for the next drill |
| Drill day-boundary defect (3 Nov, found running item 0, fixed in the tree and unreleased) | **Defect.** `restore.sh --mode=drill` on `may` failed on every chain with `scratch changed after it was sealed`: the 1 Nov chain (29 Oct full plus five deltas) and the newest (2 Nov full plus the 3 Nov delta). Every manifest unit was held, there were 0 `refusing compaction publish` lines in scratch or live, and two fingerprints of the sealed scratch 20 s apart were identical. A diff of the before and after fingerprints (from a temporary debug copy of the script) showed only the chain's last partial day, `2026-10-31` for the 1 Nov chain, growing by a few rows in each sensor table (`sensor__temperature` 56335 to 56341). The backup stopped at 17:00Z, and scratch's own `now()` was days later, so the drill counted that day as closed, and its tail appeared after the read-only restart. Earlier drills passed only because they ran the day of the backup, when that day was still open. The result was that no nightly chain could be proven. **Fix:** `restore_settled` in `restore_drill.sh` drops dated `<table>/<YYYY-MM-DD>` units from the run date minus one day onwards, from both fingerprints before they are compared. The manifest comparison for short units is unchanged. Covered by a table-style unit test. All eight modules regenerated, 101 unit tests pass. **Needs an influxdb3 release** (any module with the generated `restore.sh` picks it up on its next release). **Released in influxdb3 10.200.1926 (3 Nov 10:35) and confirmed.** Its release drill passed (chain of 3, 3384 units held, sealed), and by hand on `may` the 1 Nov chain (6 artifacts, 3262 units) and the newest chain (3 artifacts, 3384 units) both passed. The seven other modules pick the fix up on their next release. **Stale scratch is not swept:** `restore/2026-10-29_01-00-38` (1.6G) and `restore/2026-10-30_01-00-38` (851M) from `--keep-scratch` runs survived two further drills, against the *Residue* row that says the next run removes them. Delete by hand, and treat the sweep as a defect to check |
| Window A gate | Passed. Primary, secondary and tertiary succeeded for letsencrypt, zigbee2mqtt, wrangle, mariadb, plex, homeassistant, postgres and influxdb3 in a full `BACKUP_SKIP_HOURS=0 abackups start` at 09:42 on 28 Oct (the dispatcher now forwards the variable): every service exported, no `WARN` or `ERROR`, tertiary `success` (`skipped` on `raspbpi-jen`, which has no `/backup`) and `Used BKP` restored. `jil` is out of scope by decision. Window B may start; nothing waits on the 01:00 run, and each release is tested with a full `BACKUP_SKIP_HOURS=0 abackups start` instead |

A release is a rollback point (its pre-install backup), so the postgres extension update stays in its own release inside window A.

## Cleanup

### Residue from the incident, inventoried 2026-10-27

| Residue | Where | Goes when | How |
|---|---|---|---|
| Old home `10.200.1850`, 1.1G, and its install dir | may | Phase 1 | Retired by the influxdb3 release itself |
| `/tmp/backup`, 48M | may | Now | `rm -rf` by hand. It duplicates primary byte for byte and holds no full |
| Orphan deltas `2026-10-21_01-00-08` and `2026-10-22_01-00-08` | may primary | 29 Oct | Age out of primary's 7 days. Their full is only in secondary and the pin |
| Post-loss captures `2026-10-22_08-11-23` and `2026-10-22_08-15-13` | primary and secondary | Phase 6 | Deleted by hand from both, after the post-merge full is verified. They hold the empty, broken state, and restoring from them would wipe history. Tertiary snapshots keep them regardless |
| Post-loss chain `full-2026-10-26` up to the last delta before the post-merge full | primary, secondary, live server store | Phase 6 | Same as above. The post-merge full contains everything they do |
| Pin `/share/30/tmp/influxdb3-restore-2026-10-22`, 204M | may | Phase 6 | `chmod -R u+w`, then `rm -rf` |

**Phase 6 needs a forced full.** Without one, October's monthly GFS point would stay `full-2026-10-26` **forever**,
because the newest October full wins that month and the next weekly full falls in November. That point is the
nearly-empty capture. So influxdb3's snippet gains `backup.sh --full`, and phase 6 runs it straight after the merge.
Done before 31 Oct, the verified post-merge full becomes October's point. Done later, phase 6 still deletes the
post-loss chain, and October's point falls back to the newest October full that is left, `full-2026-10-19`. Either
way, the regression guard also skips any regressed run when choosing sparse points, so this cannot recur.

### Residue the design itself creates, and what clears it

| Residue | Cleared by |
|---|---|
| Scratch containers `<module>_restore` and `/home/asystem/<svc>/restore/*` | The wrapper's `EXIT` trap. Each run also starts by removing any scratch left by a killed run, and `--keep-scratch` scratch is removed by the next run with a warning |
| `cv2/quarantine/<ts>/` from the influxdb3 entrypoint | Kept until the regression anchor it caused is accepted, then removed by the next successful backup. supervisor reports while any exists |
| `--accept` markers and released anchors | Removed by the pruner once the runs they name are pruned |
| The bash pruners and the phase 3 shadow code | R2 (phase 8): `backup_pruned`, `backup_pruned_gfs`, `backup_gfs_kept`, `backup_kept_next` and the `Prune disagreement` path are deleted, and every module is regenerated |
| influxdb3's `eval "influxdb3_pruned_local () $(declare -f backup_pruned …)"` override and `influxdb3_pruned_server` | Phase 3: the server store becomes the third caller of the one pruner, so the snippet loses both |
| Parquet-engine stages 1–3 in `entrypoint.sh` (the WAL sweep, the throwaway query-mode server, the `rm` hints) | Phase 1. They are dead on PachaTree: they only run when `<data>/node_1` exists, and live's node dir is `cluster_1/node_1` |
| Stale docs: `storage/plans/filesystem.md`'s `commit=600` risk, and "`max` holds influxdb3" (it is on `may`) | Phase 1, in the same change as the `fstab` edit |
| postgres's corrupted bootstrap source and its doubly-wrapped generated output | Phase 1b, §7 |
| HA's stale migration copies, `.storage/core.entity_registry.bak-20261009140938` (3.4M) and `.storage/core.device_registry.20260810_040425.migration_backup` | Deleted in phase 1c, before the first backup |
| HA config-dir leftovers: `checkready.sh`, `influxdb-ignores.yaml`, `ui-panel-custom.yaml`, top-level `scripts.yaml`, `entities.yaml`, `python_scripts/` | Deleted in phase 1c. All six were tested unused (§8). The home copy carries every file forward on each release, so leftovers never clear on their own |
| `/home/asystem/<svc>/replaced/<run>/` from a snapshot replace | The next successful backup of that module |
| Databases left on an old TimescaleDB extension | Phase 1b, then every postgres release, §7 |
| New supervisor backup topics (`regressed`, `drill`) | Additive, so nothing is stranded. Any topic renamed during development is cleared with `mosquitto_pub -r -n`, per the repo rule |

### Residue check, the last gate of phase 9

Every line must print nothing:

```
grep -rn -E 'backup_pruned(_gfs)?\b|backup_gfs_kept|backup_kept_next|Prune disagreement|influxdb3_pruned_' src --include='*.py' --include='*.sh' | grep -v -E '/target/|/\.deps/'
ls -d src/all/_/src/build/resources/bash 2>/dev/null
grep -rn 'BACKUP_KEEP_\(DAILY\|WEEKLY\|MONTHLY\)' src --include='*.py' --include='*.sh' | grep -v -E '/target/|/\.deps/'
grep -rn 'commit=600' src | grep -v -E '/target/|/\.deps/'
ssh root@<each server> 'findmnt -rno OPTIONS | grep commit=600'
ssh root@<each server> 'docker ps -a --format {{.Names}} | grep _restore$'
ssh root@<each server> 'ls -d /home/asystem/*/restore /home/asystem/*/replaced/* /home/asystem/influxdb3/latest/cluster_1/cv2/quarantine 2>/dev/null'
ssh root@macmini-meg 'cd /home/asystem/homeassistant/latest && ls -d .storage/core.entity_registry.bak-20261009140938 .storage/core.device_registry.20260810_040425.migration_backup checkready.sh influxdb-ignores.yaml ui-panel-custom.yaml entities.yaml python_scripts 2>/dev/null; find scripts.yaml ! -newermt 2026-10-27 2>/dev/null'
ssh root@macmini-may 'ls -d /tmp/backup /share/30/tmp/influxdb3-restore-* /share/30/backup/influxdb3/2026-10-22_08-* 2>/dev/null'
for f in src/*/*/src/main/resources/image/bootstrap.sh; do [ "$(grep -c 'WARNING: This file is written' "$f")" -gt 1 ] && echo "$f"; done
for db in hass mlflow postgres template1 wrangle; do ssh root@macmini-mad "docker exec postgres psql -X -U postgres -d $db -Atc \"SELECT '$db' FROM pg_available_extensions WHERE name = 'timescaledb' AND installed_version <> default_version\""; done
ls src/all/_/src/build/resources/plans/backup.md 2>/dev/null
```

## Decided 2026-11-03: one Go engine, bash only for module specifics

Replaces the earlier "revisit the language" section. The decision is Go, for everything generic, in three releases.

### Goals, and how each is checked at the end

| Goal | Today | Done when |
|---|---|---|
| **One pruner** | Five places decide what to delete: `backup_pruned` and `backup_pruned_gfs`/`backup_gfs_kept` in `container.py`, the shadow `backup_kept_next` in `bash/backup_prune.sh`, influxdb3's own `backup_pruned` override and `influxdb3_pruned_server`, and Go's `gfsThin` (deleted in R1). Two config sources (`<MODULE>_BACKUP_KEEP_*` and `config.json`) | One keep-set function in Go serves primary, secondary, tertiary and the server-side store. Windows come from `config.json` only. The residue grep for `backup_pruned`, `backup_gfs_kept`, `backup_kept_next`, `influxdb3_pruned_` and `Prune disagreement` is empty |
| **Less complexity** | 817 lines in `bash/` (nine files), generated `backup.sh` 721 and `restore.sh` 899 lines per module, about 400 lines of wrapper templating in `container.py`, and a shell to Go vocabulary parity test | `bash/` deleted, each generated script is the module's snippets, a prelude of about 30 lines and a shim. The templating and the parity test go. Net deletion, counted at the end |
| **Generic is Go** | Lifecycle, manifest, fingerprint, guard, chain, drill, merge, file helpers and locking are bash | Every item in the generic list below is Go with table-driven tests in the suite that already runs |
| **Bash is module-specific only, from snippets** | Mixed with the wrapper | A hook is in bash only if it needs to know what the module is (the specific list below), and the generated script is nothing but those snippets plus the shim |
| **No loss of safety** | Tertiary's read-only snapshots, restore needs only the host and the script | Tertiary stays the backstop. A restore still works with supervisor stopped (pressure test, row 1) |

### Decisions

- **No shadow period.** One read-only comparison before R1 replaces it: the Go keep-set runs over every host's run trees, secondary dirs and tertiary snapshots, and any run it would delete that the old pruners keep blocks the release.
- **Tertiary moves with the rest** to the one pruner in R1, so there is one code path and one config.
- **A deletion brake** in the pruner: it never deletes the newest full or its chain, and refuses to delete more than half of a directory's runs in one pass, logging and failing the stage instead (tertiary only logs, see R1). Normal pruning removes a night or two, so it never trips. A broken keep-set trips it on its first run.
- **Three releases along the existing seam, not four stages.** `backup.sh` and `restore.sh` share almost nothing but the fingerprint parser and the lock, so the engine moves one side at a time and no release has bash calling a Go subcommand "in the interim": R1 pruning, R2 the backup side, R3 the restore side.
- **Drill gating turns on in R3**, when the weekly drills it gates on exist. Turned on earlier it would keep every sparse point forever.
- **Bash vocabulary mirrors go away.** `BACKUP_STATE_*` and the other words live in Go only once the wrapper is gone, so the parity test is deleted with it.

### The rule

**A thing is Go if it would be the same for any module, and bash if it needs to know what the module is.**

*Module-specific, stays as bash snippets:* how to produce the artifact (`backup_written`), how to put it back (`restore_applied`), the hooks that stage, seal and tear down a scratch copy (`restore_staged`, `restore_sealed`, `restore_teardown`), a live fingerprint where the artifact cannot give one (`backup_fingerprinted`, influxdb3 only), the per-unit merge (`restore_merged`), a module check (`restore_checked`), deleting a dead server-side entry (`backup_pruned_store`, influxdb3 only), and the include and exclude lists a `backup_files` module declares.

*Generic, in Go:* the run lifecycle (throttle, lock, interrupts, integrity check, atomic rename), artifact naming, the manifest, standard fingerprints (tar, zip, SQL dump), the regression guard and `--accept`, the keep-set (window, GFS tiers, chain closure, anchor, drill gating, brake), chain resolution, the drill and merge flow with progress and resume, default staging of a tar or zip, `backup_files` and `restore_files`, and the per-module lock (`syscall.Flock`, which also runs on the build machine, so the lock is finally testable).

### How Go and bash meet

- **Where the engine runs.** Inside the supervisor container, which already runs every module's `backup.sh` today from the read-only `/var/lib/asystem/install` mount, with `/home/asystem` writable, the Docker socket, and `bash`, `docker`, `rsync`, `jq`, `unzip` and `util-linux` in the image. Nothing new is needed in the container.
- **How a host caller reaches it.** `install.sh` and a hand-run `restore.sh` run on the host as root. The shim runs `docker exec supervisor supervisor <verb> ...` when the container is up, and otherwise `docker run --rm` of the installed supervisor image with the same mounts and the engine as entrypoint. The installer keeps the previous version's image, so a supervisor release can still run the old engine for its own pre-install backup.
- **How Go calls a hook.** `bash -c 'set -a; source <module .env>; source <module snippets>; <hook>'`, every call bounded by a timeout, the hook's stdout as data and its exit code as verdict. An optional hook is detected with `declare -F`, and absent means the Go default. `.env` is sourced the way `backup.sh` does today, so the `SERVICE_*` rule in the root `CLAUDE.md` is unchanged.
- **Config.** Windows (`BACKUP_RETAIN_DAYS` and the three `BACKUP_KEEP_*`) are read from `config.json` only, filled by supervisor's generator from each module's `.env_all`. Every other module setting (`*_BACKUP_SHRINK_PERCENT`, `*_BACKUP_LIVE`, `RESTORE_SERVICE_STATE`, the include and exclude lists) stays in the module's `.env` and snippets and is read by the engine from there.
- **Skew.** The engine exposes a small integer contract version. Additive changes never bump it, and the shim refuses to run against an older engine, skipping the backup loudly. Supervisor therefore releases before any module that needs a newer contract, and a module release never needs a supervisor rollback to be undone.

### The three releases

| Release | Ships | Replaces | Module releases | Gate |
|---|---|---|---|---|
| **R1 Pruning** | The keep-set in `probe_util_backup_keep.go`, with brake, anchor and chain closure. Primary stage prunes the local run dirs after the script exits, secondary prunes the share, tertiary prunes snapshots, and influxdb3's dead server-side entries are left to R2's `backup_pruned_store`, not done in R1. Supervisor sets `BACKUP_PRUNE=false` when it runs a script | `gfsThin`, and secondary's call to `backup.sh --prune-gfs` | None. Pre-install and hand-run backups keep the old pruners until R2, which is no change from today | The read-only comparison is clean on every host. The brake bites (a unit test over real directories, and on `jen`'s backlog on 3 Nov). Two consecutive hand-run full backups complete on every host with tertiary. Met 2026-11-03 |
| **R2 Backup side** | `probe_util_backup_run.go`, `_manifest.go`, `_fingerprint.go`, `_guard.go`, `_hooks.go`. `backup_files` and `backup_target` become prelude one-liners calling the engine. influxdb3 gains `backup_pruned_store` | `bash/backup_*.sh`, the generated `backup.sh` wrapper, every bash pruner and the shadow code, the `BACKUP_KEEP_*` defaults in `container.py` | All eight, in rising order of cost (letsencrypt first, influxdb3 last) | Each module's manifest is byte-identical to the bash-written one for the same artifact and its fingerprints are unit-for-unit equal. Each pre-install and next nightly run succeeds |
| **R3 Restore side** | `_chain.go`, `_drill.go`, `_merge.go`, `restore_files`, the lock. Weekly GFS-synced drills in secondary, the `drill` states, `Fail BKP` reading the newest `drill.json`, and drill gating on | `bash/restore_*.sh` and `asystem_lock.sh`, the generated `restore.sh` wrapper, then the whole `bash/` directory | All eight, same order | Release drill green per module. A truncated artifact fails by name. A planted failed drill turns `Fail BKP` red, which is phase 2's failed-drill half carried over from R1, and the point is kept but counts for nothing. Every existing sparse point drilled once |

Each release is verified against the real data already on the hosts, run read-only: keep-set decisions run by run, manifests byte for byte, fingerprints unit by unit. Tests are ported from the bash suite before any bash is deleted.

### Pressure test, 2026-11-03

The plan checked against the code and the goals above.

| # | Finding | Evidence | Resolution |
|---|---|---|---|
| 1 | **Host callers cannot rely on a running supervisor.** `install.sh`'s pre-install backup and release drill, and a hand restore, run on the host. A restore is most needed after something has broken, and a supervisor release replaces the engine mid-install | The old plan said restore "would depend on a healthy supervisor install" and left it as a cost | The shim falls back to `docker run --rm` of the installed supervisor image, and the previous image is kept. The engine is a CLI verb, so it works with the supervisor container stopped. A rebuilt host needs the supervisor image installed first, which its bootstrap already does |
| 2 | **Interim bash to Go bridges.** The earlier four stages had the wrapper call Go subcommands for manifest, guard and chain "in the interim", then be rewritten | Stage 2 text | Cut along the `backup.sh`/`restore.sh` seam into R1 to R3. No release has bash calling the engine except the final shims |
| 3 | **Eight module releases just to stop pruning.** Stage 1b had every module script set `BACKUP_PRUNE=false` | Primary's `exec.CommandContext(ctx, "bash", script)` already builds the script's environment, and `BACKUP_PRUNE` already exists and defaults true | Supervisor sets it for its own runs. R1 needs no module release. Pre-install and hand runs prune with the old code until R2 deletes it, which is no riskier than today |
| 4 | **Drill gating before drills keeps everything forever** | A point counts only with a green `.meta/secondary/drill.json`, and nothing writes one until §5a exists | Gating is added in R3 together with the weekly drills, which are Go there and so do not call `bash restore.sh` |
| 5 | **Tertiary is the backstop and the first thing new code would prune** | `gfsThin` thins snapshots; the old rollout table names tertiary as the answer to "a bad prune anywhere" | One pruner is still the goal, so the protection moves into the pruner: the brake, never deleting the newest full or its chain, and the comparison run including snapshots. A bug can still drop old sparse points on all three tiers at once, which is accepted |
| 6 | **Locking was untested** | "The per-module `flock` is untested because the build machine has no `flock`" | `syscall.Flock` in Go runs on the build machine, so it gets a test. The lock file lives on the shared `/home/asystem` mount, so a shim run on the host and the engine in the container contend on the same file |
| 7 | **Hook environment** | `install.sh` sources `.env` without exporting it, so a hook sees no `SERVICE_*` variables unless listed in `resources.txt` | The hook runner sources the module `.env` itself, as `backup.sh` does. Covered by a test that a hook reads a `SERVICE_*` value |
| 8 | **Timezone and run names** | Run names are Perth local time and the supervisor container sets `TZ` | The engine formats names in `TZ` as the container sees it, with a test against an existing run directory name |
| 9 | **Config drift between two sources** | `<MODULE>_BACKUP_KEEP_*` in the module env and `BackupKeep*` in `config.go` | Windows move to `config.json` only (above). A test fails the build if a module's `.env_all` window has no entry. R1 fills the `modules` map in supervisor's `generate.py`, but this test is still to write in R2 |
| 10 | **A skewed module and engine** | A pre-install backup runs the new release's snippets against whatever engine the host has | Contract version and a loud skip (above). Supervisor first is the release order for every contract bump |
| 11 | **Rollback after R2** | `BACKUP_PRUNE=true` restores script pruning only while scripts still have it | After R2 rollback is relinking the previous supervisor, and a module that needs the newer contract skips loudly until it is rolled back too. Recorded so it is not a surprise |
| 12 | **Retention of supervisor's own run trees** | `pruneRuns` and `pruneStale` prune run logs and stale entries, not backups | Out of scope: a separate, smaller concern. The residue grep does not match them |
| 13 | **Engine size** | About 1500 lines of Go across eight files in one package, since a sub-package was rejected | Held to supervisor's `CLAUDE.md` rules: no comments, table-driven tests, `[$VAR]` messages, `scribe` logging. Counted against the deleted 817 bash lines, the 1600 generated wrapper lines per module and the templating |
| 14 | **Module-specific logic leaking into Go** | Risk of the engine learning about influxdb3. Checked 2026-11-03: the existing backup Go holds no module name outside test fixtures. Three leaks the plan would otherwise introduce are below | The rule: any `if module ==` or product-specific format in the engine is a defect, and the answer is an optional hook or a declared parser. (a) **Open units.** The drill fix `restore_settled` recognises unit names ending in `/YYYY-MM-DD`, which is influxdb3's convention. In Go the module declares which units are still open through the existing `backup_durable` shape, or the fingerprint marks them, and the engine never parses unit names. The bash `restore_settled` is the stopgap until R3. (b) **SQL-dump fingerprints.** The `COPY` line count (`pg_dump`) and the `-- Current Database:` split (`mysqldump`) are named parsers the module selects by declaration, not by sniffing the file. (c) **Merge needs deltas.** That check stays in `fab generate` (Python) and the engine does not repeat it |

### What the existing Go already provides

Supervisor already uses the Docker SDK and has labelled test containers, so drills and merges get real-container tests in the suite that already runs. `scribe` and the run tree give restore, drill and merge the same columns as a backup in `abackup tail`, which makes the label-alignment work in `restore_report` unnecessary. `bounded` and `stageExec` enforce the repo's timeout rule that the bash applies case by case. `backupRuns`, `newestBackupDir`, `treeRunPattern` and `parseBackupArtefact` already list runs and name artifacts. `readManifestVerdict` already reads the manifest, so one struct ends the two-language parse. `abackup` gains `run`, `accept`, `restore`, `drill` and `merge` beside `list`, `tail`, `start`, `stop` and `clean`.

### Post-R3 review

After R3's gate holds and before the plan is folded into `CLAUDE.md` and deleted, run the review below over all backup and restore code. It was run over the R2 backup side on 5 Nov and found a real defect (plex's `backup_completed` relied on a variable set by another hook, which stopped working when each hook got its own `bash`) as well as dead code, a test asserting message text, and a missing test of the `files` verb. The instructions, as given:

> Code review the backup code in `_` and supervisor and the backup script snippets thoroughly. Can it be simplified, and is it correct? Make sure project guidelines are followed. Check all logic. Make sure the style stays in sync with the backup and other modules. No comments except for clear exceptions, such as documenting an interface or a complicated process. Check for simplifications, dead code, unit test gaps and unit tests that aren't valuable (for example tests of log statements). Reorganise structs, vars and funcs by project guidelines. Inline single-use helpers, and use closures for helpers used more than once but local to one function. Make sure all tests conform to the project standard and norm, including naming and shape.

*Scope for the R3 pass.* `src/all/_/src/build/python/asystem/container.py` (the generated wrappers and contracts), `src/all/_/src/build/resources/bash/` (should be gone), the supervisor `probe_util_backup*.go` files and their tests, `cmd/cmd_backup.go`, `engine_impl_backup.go`, every module's `src/build/resources/{backup,restore}.sh` snippet, the generated scripts, the Python unit tests in `src/all/_/src/test/python/unit/` and the influxdb3 module's `unit_test.py`.

*Method.* Follow the ten passes in the global `~/.claude/CLAUDE.md` section *Code review and refactoring*, which generalises this review. The R2 pass found, in the order of those passes: a cross-hook state defect (plex), two constants only tests used, a test asserting message text, three readers of `manifest.json` where one was needed, a missing test for the `files` verb, and three names that clashed after the CLI refactor. Expect R3 to have the same kinds: restore hooks that share state across the engine's `bash` calls, a second reader for `drill.json`, and a drill or merge helper that exists only for its test.

### Exit

Stage 1 is no longer a first slice. All three releases are scheduled. When R3's gate holds, run the *Post-R3 review* above, fold the durable rules into supervisor's `CLAUDE.md` Backup section, run the residue check, and delete this plan.
