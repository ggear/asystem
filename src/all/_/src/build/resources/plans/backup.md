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
enough, because every module that writes manifests ships its own `backup.sh`.

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
| One pruner owns every keep decision | supervisor's `gfsThin` thins tertiary snapshots and any secondary dir without an executable `backup.sh` | Refuses manifest-bearing dirs (§3) |
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
| A new pruner deletes what the old one kept | `install.sh` runs the **new** release's `backup.sh` for the pre-install backup, which prunes too, and supervisor's secondary stage calls that same script's `--prune-gfs`. New pruning code is live the moment a module installs | Shadow pruning, below |
| A sidecar is read as the artifact | Three readers take the run dir's first file (§1) | The name-pattern selection ships in phase 3 before any manifest is written, and sidecars live in `.meta/` |
| A run without a manifest is misread | Every run before the rollout has none | No manifest means its parent is inferred by order, as GFS does today, and it is never deleted on manifest evidence. Its fingerprint is "unknown", which never triggers or releases an anchor |
| supervisor rejects an unknown backup state | `regressed` and `drill` are new words in a vocabulary `metric_schema.go` owns | supervisor releases first, with both words and the parity test |
| The influxdb3 restarts | each release, and the merge, restart it | Accepted: a few seconds of supervisor metrics, nothing from HA (*Settled 2026-10-27*) |
| The merge writes wrong data into live | it is the only step that writes history into production | Safety backup first, plan read before `--force`, verified after a restart. The pinned chain stays until a new full covers it |
| A plex restore before phase 4 corrupts its databases | Today's `restore_files` extracts over live, leaving live's `-wal`/`-shm` beside the restored `.db` files (§8, round 3) | Until phase 4 ships wholesale replace, a plex restore by hand stops plex, moves `Plug-in Support/Databases/*-wal` and `*-shm` aside, then runs `restore.sh`. Moving them while plex runs would leave it writing to an unlinked WAL |
| A bad prune anywhere | | tertiary's read-only snapshots, which every phase leaves untouched. Tertiary ran on every host every night through 27 Oct |

**Shadow pruning.** For the first release of each module, the new pruner computes its keep set and the old pruner's,
and deletes only what **both** would delete. Every disagreement is logged, as `Prune disagreement` with the run and
both verdicts. By construction the new keep set is a superset: a longer window, plus chain closure, plus the anchor.
Any run the new pruner would delete and the old would keep is a bug, and the phase stops there. The old pruner goes
once every module has shown 7 nightly runs with no disagreement.

### Phases

Each phase ends at its gate. Nothing in the next phase starts until the gate holds.

Until phase 6, the pinned copy is the only protection for the incident chain that no pruner will touch. Phase 1's
influxdb3 release retires `/home/asystem/influxdb3/10.200.1850`, the old home holding the server-side copy of the
chain. Secondary's GFS drops `full-2026-10-19` around 23 Nov unless phase 3 has raised the window by then. Both
are expected, and neither matters while the pin holds.

| Phase | Ship | Gate |
|---|---|---|
| 0 | ~~Pin the incident chain~~ Done: `/share/30/tmp/influxdb3-restore-2026-10-22/` | five runs, `cmp` and `gzip -t` clean |
| 1 Durability | Drop `commit=600` from the four `fstab` sources, and apply it with `mount -o remount,commit=5` on each mount (no reboot needed). influxdb3 `entrypoint.sh` quarantine-and-refuse | `findmnt -no OPTIONS` shows no `commit=600` on any host. A drill on scratch: zero-length checkpoints make the entrypoint refuse to start, with the quarantine dir populated |
| 1b postgres | §7: the bootstrap fragment restored, then the extension update added to it. One postgres release | Every database reports `extversion = default_version`. The generated `image/bootstrap.sh` holds the banner once. The pre-install backup taken just before this release stays as the rollback point until phase 4's drill of a post-update dump is green |
| 1c homeassistant | First, `backup_files`' tar changes, as a framework change: stderr to the run log, and the exit-1 retry for a module declaring `_BACKUP_LIVE=atomic`. Without them a running HA copy fails intermittently with no reason (§8, round 3). `backup_files` is inlined into each generated `backup.sh`, so regenerate every module, read every `backup.sh` diff, and release each module whose script changed (plex, letsencrypt and wrangle call it). Then stderr reaches the run log for every module once 1c lands, and phase 3's diffs hold only phase 3's change. Then delete the two stale `.storage` migration copies and the six tested leftovers (§8), and enrol `.storage`, `custom_templates` and `blueprints`, excluding `.storage/tmp*`, `*.bak-*` and `*.migration_backup`, in a homeassistant release. The enrolment is additive: it gains manifests in phase 3 like every other module | Every module whose `backup.sh` changed is released, and its next nightly run succeeds. The next nightly run shows homeassistant in primary and secondary. `backup_files` reports no unmatched entry. A bare `restore.sh` prints a plan naming exactly the three includes. The archive extracts into scratch |
| 2 supervisor | `regressed` and `drill` states in `metric_schema.go`, the shell mirror, the parity test. A `regressed` run feeds `BKP` (false) and `Fail BKP` (a failed stage); a failed drill feeds `Fail BKP` only (§5a). The two descriptions widen (§2). Primary reads a new run's `.meta/manifest.json` after the script exits, records `regressed` beside `SuccessBool`, which stays true so secondary still promotes, and writes the evidence lines to `run.log` (§2). Secondary logs `drilled [...]` per drilled point, and primary logs release drills from `.meta/primary/drill.json` (§5a). A failed drill holds `Fail BKP` non-zero across runs: each run reads the module's newest `.meta/secondary/drill.json`, not only its own roll-up, until a later drill is green. Report a run whose local `status.json` is missing after its timeout as failed. Also write a `failure` `status.json` for a service primary refuses before starting it (container not running, or `health: starting`), which today leaves its service dir empty and so no state at all (seen on `meg`'s `homeassistant`, 2026-10-28 09:14) | supervisor released to every host, parity test green, existing backup states unchanged in HA, a planted `regressed` run on a test module turns `BKP` false and `Fail BKP` non-zero, still reaches the share, and `backup tail` of that run shows `as [regressed]` with its evidence line and a failed result; the next skipped run of that module does not re-report it; a planted failed drill shows the same way in the secondary cell, and two consecutive nightly runs complete on every host with tertiary |
| 3 Backup side | Manifest, fingerprints, regression guard (report only: it publishes `regressed` and pins an anchor, but nothing waits on `--accept`), chain-aware pruner in shadow mode, influxdb3's raised window. Regenerate every module and read every generated `backup.sh` diff. Release in rising order of what a mistake would cost: letsencrypt, zigbee2mqtt, wrangle, homeassistant, mariadb, postgres, plex, influxdb3 | Per module: its pre-install and next nightly runs each write a manifest, no `Prune disagreement`, and secondary's GFS log deletes nothing it did not delete before |
| 4 Restore side | Restore wrapper with chain resolution, `--source`, `replace`/`drill`/`merge`, and every wrapper-held invariant. Each module's staging, sealing and fingerprint hooks. `install.sh` drills after start, as a warning. `fab generate` fails a module defining `restore_merged` without deltas. postgres `restore_applied` rewritten per *Pressure test*, with the extension update after a `replace` (§7). Wholesale replace in `restore_files`, with exclude carry-back and no SQLite sidecars (§8). The per-module `flock` | Per module: its release drill is green. A deliberately corrupted artifact (`--file` pointing at a truncated copy) fails the drill by name, so the drill is shown to bite |
| 5 Recover | influxdb3 `restore_merged`. A drill against the pinned chain, then a bare `merge` run to read the plan, then `--force` | Plan lists every table's days 2026-08-13 → 2026-10-21 and nothing after. The post-restart fingerprint holds every unit. HA's log has no `Catching up, dropped`. Grafana shows the history |
| 6 Release the pin | `backup.sh --full` straight after the merge. Wait for its secondary copy and tertiary snapshot. Then do the incident cleanup in *Cleanup* | That full's fingerprint covers every unit of the staged chain's. Only then delete the post-loss runs and the pin |
| 7 Steady state | Remove the old pruner after 7 clean nights per module. The regression guard enforces (an anchor holds until `--accept`). GFS-synced weekly drills (§5a) start, and pruning requires a green `.meta/secondary/drill.json`. Every existing sparse point is drilled once to backfill it. Until then it counts for nothing and is kept, which is safe but is residue | Fold the durable rules into supervisor's `CLAUDE.md` Backup section, and delete this plan. The residue check below comes back empty |

### Where this stands and what is next (2026-10-28)

Window A (phases 1, 1b, 1c) is written, released and verified (progress table below), and its gate is closed. Phase 2 is partly written in the working tree (below), unreleased, and phases 3 to 7 are not written. Nothing is committed: the work sits unstaged in the working tree.

**Next, in order**
1. Window A is closed. A full manual run at 09:42 on 28 Oct passed on all five hosts, and the leader election was healthy after the 10.200.1888 restart (`mad` led, all hosts agreeing). Phase 2's release is tested by a full `BACKUP_SKIP_HOURS=0 abackups start` after it, not by waiting for the 01:00 run.
2. Finish phase 2 (supervisor Go) and release it to every host before anything else in window B. **Written and tested, unreleased:** `BackupStateRegressed` in `metric_schema.go`; the service payload's `regressed_bool` beside `success_bool`; primary reading a new run's `.meta/manifest.json` after the script exits (`readManifestVerdict`) and setting the service to `regressed` with `success_bool` true, logging each `evidence` line at WARN and failing the primary stage; `BKP` false for a regressed service; both descriptions widened; schema regenerated. **The manifest contract phase 3 must write:** `{"verdict": "regressed" | "accepted", "evidence": ["<line>", ...]}`, the verdict word being `metric.BackupStateRegressed` and absent or unreadable meaning no verdict. **Still to write:** the `drill` state and the failed-drill path (needs §5a, so it waits for phase 4's `restore.sh --mode=drill`), a shell mirror of the state words with its parity test (the first shell consumer is phase 3's manifest writer, so write both together there), `Fail BKP` reading the newest `drill.json`, and the planted-run gate test on a real host after release. **Written since:** the `failure` `status.json` for a service primary refuses before starting it (`BKP` now reads false for it, as the stage already read failed). A run with no local `status.json` after its timeout needed nothing: a scheduled run past its ceiling already reads fully failed, and a hand run is deliberately walked past
3. Phase 3 in `container.py`, all unreleased and regenerated for the eight modules with every `backup.sh` and `restore.sh` shellchecked. **Written:** (a) the artifact-by-name fix for the three first-file readers; (b) the manifest, `.meta/manifest.json` with `kind`, `parent`, `source_version`, `verdict`, `accepted`, `baseline`, `evidence` and the `fingerprint`, written after every successful run and never failing it; (c) default fingerprints per artifact type from the archive itself (tar bytes per declared include, zip bytes per entry, postgres rows per `COPY` table, mariadb bytes per database) and influxdb3's own `backup_fingerprinted`; (d) the report-only regression guard, with `<MODULE>_BACKUP_SHRINK_PERCENT` (default 20, 0 disables the percentage test), the evidence capped at 20 lines, `backup.sh --accept=<run>`, and the anchor derived at prune time; (e) the shadow pruner, where the old pruners only delete what the next keep set also drops and log `Prune disagreement` for the rest, the next windows read as `<MODULE>_BACKUP_NEXT_{RETAIN_DAYS,KEEP_DAILY,KEEP_WEEKLY,KEEP_MONTHLY}` and set for influxdb3 in its `.env_all` as 14 days, 8 weekly, 12 monthly; (f) influxdb3's full on the first run of each ISO week; (g) the shell mirror `BACKUP_STATE_SUCCESS` and `BACKUP_STATE_REGRESSED` in `backup_manifest.sh`, with a supervisor test holding them equal to `metric_schema.go` that fails on a planted mismatch. The wrapper has 16 unit tests in `src/all/_/src/test/python/unit/unit_test.py`, run by hand with the asystem `pytest` and needing GNU `find` and `date` on the path locally, since no build runs them. **Not proven offline, so read in the first release of each module:** the tar listing parse against GNU tar on the hosts (the tests run against bsdtar), the real postgres and mariadb dump shapes, and influxdb3's live query, whose failure shows as an empty fingerprint and a `Manifest could not be written` or `regressed` line. Release the modules in the order in the phases table, and read `abackup list` and the run's `.meta/manifest.json` after each. **Released so far (28 Oct, tests skipped):** letsencrypt, zigbee2mqtt, wrangle, homeassistant, mariadb, postgres (10.200.1895), plex (10.200.1896) and influxdb3 (10.200.1897). Each pre-install run wrote a `.meta/manifest.json` with `verdict` `success`, an empty `baseline` as expected for a first manifest, and a populated fingerprint (letsencrypt 4 units, zigbee2mqtt 8, wrangle 4). That proved the GNU tar listing parse on the hosts for the tar modules (bytes per declared include) and the zip parse for zigbee2mqtt. The artifact reader still picks the archive in the newest run on each host, there is no `Prune disagreement` or `Manifest could not be written` in any supervisor or module log, and the only pruning lines seen are the old pruner's from runs before the release. homeassistant wrote 3 units, its three enrolled includes (`.storage`, `blueprints`, `custom_templates`), and mariadb 2 units, the databases `mysql` and `weewx`, so the mariadb dump parse is proven on a real dump; both newest runs hold only the archive, neither log shows a `Prune disagreement` or `Manifest could not be written`, and both containers were `healthy` within about a minute of the release. postgres wrote 147 units (`<database>.<schema>.<table>` row counts: 28 in `hass`, 79 in `mlflow`, 20 each in `postgres` and `template1`), 14 of them non-zero, the largest being `hass.public.statistics` at 3 353 206 rows, which matches the 147 `COPY` lines counted on the 22 Oct dump, so the postgres parse is proven on a real dump. The zero-row units are the empty `mlflow` tables, the TimescaleDB catalog and the five transient `hass` tables whose data is excluded by design, and the total is dominated by `statistics`. The container was `healthy` 33 s after the release. plex wrote 2 units, its two enrolled includes (`Plug-in Support` at 719 666 904 bytes and `Preferences.xml` at 791) from a 540 MB archive, the container was `healthy` 26 s after the release, and the run holds only the archive with no `Prune disagreement` or `Manifest could not be written`. influxdb3 wrote a `delta` manifest with `parent` `2026-10-26_01-00-36` (the post-loss full of that ISO week, so the ISO-week rule correctly chose a delta on a Wednesday) and 253 units over 44 tables, `<table>/<day>` row counts of the closed days 2026-10-22 to 2026-10-27 plus one stray unit dated 2025-10-13, so the live query hook is proven on the real database. That also shows the live database still holds only post-loss history, which is the state the guard now baselines and which phase 5's merge will only grow. The `INFLUXDB3_BACKUP_NEXT_*` windows (14 days, 8 weekly, 12 monthly) reached the installed `.env`, the run holds only the archive, there is no `Prune disagreement` or `Manifest could not be written`, and the container was `healthy` 27 s after the release. The stray 2025-10-13 unit is a closed day with a count, so if that single row ever ages out the guard will name it as missing and regress the run: if so, accept it with `backup.sh --accept=<run>` or exclude it with `backup_durable`. **Read after two further full runs (12:02 and 12:04 on 28 Oct):** every one of the eight modules wrote `verdict` `success` with the previous run named as `baseline` (letsencrypt 4 units, zigbee2mqtt 8, wrangle 4, plex 2, postgres 147, homeassistant 3, mariadb 2, influxdb3 253), so the guard did not false-positive on wrangle's renamed bank files or on plex's databases, and no `Prune disagreement` or `Manifest could not be written` appeared in any module or supervisor log. The 01:00 scheduler run is not a gate. **Previously still to read for these eight:** the next nightly run, whose manifest must name the pre-install run as `baseline` with `success` (wrangle's bank files are the first real test that the guard does not false-positive), with no `Prune disagreement` and no run deleted that the old pruner would have kept. **Not yet released:** supervisor only. Every fingerprint parser is now proven on real data.
4. Window C. **Phase 3 loose ends, written, unreleased:** `gfsThin` refuses any directory whose runs carry a `.meta/manifest.json` (table-tested), and the wrapper's `backup_target` refuses a delta with no local full to hang off, with influxdb3 falling back to a full instead. **Phase 4, written generically and unreleased, 30 wrapper tests pass, each generated script shellchecked:** (a) `restore.sh` takes `--mode=replace|merge|drill`, `--source`, `--record=<stage>` and `--keep-scratch`; (b) it resolves the chain, the full named by the target's manifest `parent` plus every delta up to it, with an inferred parent for pre-manifest runs, searching primary then `/share/*/backup/<svc>`, or only `--source`, and runs an integrity check on every artifact; (c) the default `--from` is the newest run that is not regressed, and naming a regressed run needs `--force`; (d) `drill` stages into a scratch directory, checks the artifact and the scratch both hold at least the manifest's count for every unit, seals the scratch read only and checks it did not move, tears it down, and records `success` or `failure` in `<run>/.meta/<stage>/drill.json`; (e) `merge` is refused by name for a module with no `restore_merged`, and with one it plans the closed units that differ from live, applies them only with `--force`, records each finished unit so a rerun skips it, restarts live, and faults naming any unit still short; (f) a per-module `flock` shared by `backup.sh` and `restore.sh`, and the restore's safety backup runs with pruning off; (g) `install.sh` abandons an install whose pre-install backup comes back regressed, or was skipped because the container was not running, unless forced, with the decisions exercised against stubs; (h) the fingerprint parser is one shared source for backup and restore. **Rehearsed on 28 Oct, all unreleased, nothing production written:** the influxdb3 hooks (`restore_staged`, `restore_sealed`, `backup_fingerprinted` by address, `restore_merged`, `restore_teardown`) were run from the generated `restore.sh` on `may` against the pinned incident chain. A drill took 49 s and left nothing behind. A bare `--mode=merge` against the real live planned 2883 units and changed nothing: every table's days from 2026-08-13 to 2026-10-21, none of them held by live, and `sensor__temperature` totalling 4 907 096 rows as the plan says. The merge itself was applied with `--force` to a separate throwaway container standing in for live, never the real one. That full rehearsal, `restore.sh --mode=merge --force --no-backup` with six concurrent jobs, merged the 2286 units the stand-in still lacked in about 20 minutes (a serial run was heading for an hour), then restarted the stand-in and passed the wrapper's own check that every planned unit held at least the backup's count. Checked independently afterwards: all 2883 scratch units identical in the stand-in, `sensor__temperature` 4 907 096 rows with the same first and last timestamps, 84 distinct entities and the same value checksum, `automation` 16 714 and `binary_sensor` 2 566 rows identical, two live-only points written beforehand still present, and the counts unchanged after a further restart. The real merge uses `http://127.0.0.1:${INFLUXDB3_API_PORT}` and `INFLUXDB3_TOKEN_ADMIN` from the installed `.env`, which a read-only check showed authenticate (health 200, 401 without the token). Findings that changed the code: (1) the restore chain must follow the preceding run, not the nearest full, because every influxdb3 delta hangs off the previous backup, and the manifest `parent` of a delta is now the previous run (manifests written before this change name the full, so the resolver follows the preceding run and reports any disagreement); (2) a fingerprint's row order is not stable, so both the hook and the wrapper sort before comparing; (3) a count taken seconds after a restart undercounted by 55 000 rows of a day that was in fact fully written, so verification retries until the counts settle (`RESTORE_VERIFY_ATTEMPTS`, `RESTORE_VERIFY_SLEEP`); (4) each `write_lp` call costs about a second and one big write is refused with 413, so a unit is chunked by 4 MiB (`INFLUXDB3_RESTORE_CHUNK_BYTES`) and units can merge concurrently (`RESTORE_MERGE_JOBS`); (5) the resume record lived inside scratch, which restaging deletes, so it now sits beside it as `<run>.merged`; (6) postgres sealing failed silently for later databases once `postgres` was read only, so it seals over sessions that opt out and a failed seal is a fault. Also done: the postgres hooks (staged scratch, transform with the `CREATE ROLE postgres` line dropped and `pre_restore` and `post_restore` around the catalog load, sealed, fingerprinted by address, `restore_applied` dropping each dumped database first), proven locally with the real `backup.sh` and `restore.sh` on a TimescaleDB cluster for both a drill and a replace after damage, and on `mad` as a drill of the real newest dump (147 units held, 15 s); plex's `PRAGMA integrity_check` through a generic `restore_checked` hook, drilled on `mad` against the real 516 MB backup (both databases `ok`, 13 s); the post-start release drill in `install.sh`, recorded in the pre-install run's `.meta/primary/drill.json` and only ever a warning; and `fab generate` refusing a module that defines `restore_merged` without deltas. **Not done:** the postgres extension version for a dump taken before the extension update (set `POSTGRES_RESTORE_TIMESCALEDB_VERSION`, but the image carries only 2.30.x so such a dump cannot be loaded as is); the mariadb scratch container (`meg` is not authorised for rehearsal); dependents stopped during a replace; tertiary reached only through `--source`; the `flock`, untestable on this Mac; and the real merge itself, which is phase 5. **Next gate, one batch release of everything unreleased** (28 Oct, tests skipped because `fab generate` has run for all): `letsencrypt`, `zigbee2mqtt`, `wrangle`; then `homeassistant`, `mariadb`; then `postgres`, `plex`; then `influxdb3` (it carries the corrected manifest `parent`); then `supervisor` last. From `src`, one module per `fab release` run, stopping at the first failure. `install.sh` is now stricter, so a release abandons its install when the pre-install backup is regressed or skipped, a stopped container counting as skipped, unless `FAB_FORCE_INSTALL=1`. Unrelated working-tree changes will ride along in the release commits: the `mbpfan` fan block in `_debian`, `_fedora` and `_fedora_max` `install.sh`, `wrangle`'s `postgres/document.json` and 13 `zigbee2mqtt` payloads (generator drift). **Gate checks after the batch:** each module's pre-install run carries `.meta/primary/drill.json` with `success`; a deliberately truncated copy of an artifact passed to `restore.sh --mode=drill --file=` fails by name with "failed its integrity check"; and the new influxdb3 manifests name the previous run as `parent`. **Then phase 5**, in two steps on `may`: first `restore.sh --mode=merge --from=2026-10-22_01-00-08 --source=/share/30/tmp/influxdb3-restore-2026-10-22` bare, which must list 2883 units and nothing after 2026-10-21; then the same with `--force` and `RESTORE_MERGE_JOBS=6`, which takes a safety backup of live first. The old manifests written on 28 Oct name the full as `parent`, which the resolver tolerates. Afterwards the post-restart fingerprint must hold every unit, Home Assistant's log must show no `Catching up, dropped`, and Grafana must show the history. Then phase 6 (a fresh `backup.sh --full`, then the cleanup), then phase 7 after 7 clean nights. 

**Facts that are not obvious from the code**
- Hosts: ssh as `root@macmini-{mad,meg,may,max}` and `root@raspbpi-jen`. `jil` does not resolve and is out of scope.
- `abackups start` now forwards `BACKUP_SKIP_HOURS` to each host (numeric only, else exit 2). The 09:42 run on 28 Oct confirmed it: no service was throttled. The dispatcher ran from `rue`, a client host, and each supervisor release installs its own copy of `backups.sh` there. So the change reaches a dispatching host with a supervisor release. Where a copy predates it, `ssh root@<host> 'BACKUP_SKIP_HOURS=0 abackup start'` does the same. No other `BACKUP_*` variable should be forwarded: `BACKUP_SERVICE_RESTART` is set by supervisor itself and `BACKUP_HOME_ROOT` is a test override.
- A hand-run `abackup start --stage primary|secondary` writes a run with no tertiary document, which blanks `Used BKP` until the next full run. Set `BACKUP_SKIP_HOURS=0` to defeat the throttle. A fresh release is `health: starting` for a while and primary refuses it.
- Plex stops for about 22 s whenever its backup runs, whether by hand or by stage.
- An entrypoint drill must set `INFLUXDB3_DATA_DIR=/asystem/mnt`, because the image defaults to another path.
- Restoring a delta replaces the source's whole state, so never restore the post-loss runs `2026-10-22_08-11-23` and `2026-10-22_08-15-13`.
- The pin `/share/30/tmp/influxdb3-restore-2026-10-22/` is the only protection for the incident chain besides secondary, until phase 6.
- Each postgres release costs HA about 70 s of recorded states.
- The hand rules from CLAUDE.md apply: read-only git, no edits to `entity_metadata.xlsx`, `shellcheck` on every script, `[$VAR]` log messages.

### Release windows

Phases are written and gated one by one, but released in three windows. A window ends at its gate, and nothing in the next starts before it holds.

| Window | Phases | Order inside | Gate before the next window |
|---|---|---|---|
| A | 1, 1b, 1c | `fstab` remount on each host (no release); homeassistant leftovers and stale `.storage` copies deleted on meg; every module whose generated `backup.sh` or `restore.sh` changed (plex, letsencrypt, wrangle, others after reading the diffs); homeassistant; postgres; influxdb3 | `findmnt -no OPTIONS` shows no `commit=600`; every database at `extversion = default_version`; each released module's next nightly run succeeds; homeassistant shows in primary and secondary; the influxdb3 scratch drill refuses on zero-length checkpoints |
| B | 2, 3 | supervisor to every host first, then modules in rising cost: letsencrypt, zigbee2mqtt, wrangle, homeassistant, mariadb, postgres, plex, influxdb3 | phase 2 gate on every host; then per module a manifest on its pre-install and next nightly run, no `Prune disagreement` |
| C | 4, then 5 and 6 as runs, then 7 | each module's release drill; the merge is a production run, not a release | release drill green per module and the truncated-artifact drill fails by name; phase 5 and 6 gates; phase 7 needs 7 clean nights per module, which no release shortens |

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
| Shadow pruning, and the old pruner it compares against | Phase 7: `backup_pruned`, `backup_pruned_gfs` and their `Prune disagreement` path are deleted from `container.py`, and every module is regenerated |
| influxdb3's `eval "influxdb3_pruned_local () $(declare -f backup_pruned …)"` override and `influxdb3_pruned_server` | Phase 3: the server store becomes the third caller of the one pruner, so the snippet loses both |
| Parquet-engine stages 1–3 in `entrypoint.sh` (the WAL sweep, the throwaway query-mode server, the `rm` hints) | Phase 1. They are dead on PachaTree: they only run when `<data>/node_1` exists, and live's node dir is `cluster_1/node_1` |
| Stale docs: `storage/plans/filesystem.md`'s `commit=600` risk, and "`max` holds influxdb3" (it is on `may`) | Phase 1, in the same change as the `fstab` edit |
| postgres's corrupted bootstrap source and its doubly-wrapped generated output | Phase 1b, §7 |
| HA's stale migration copies, `.storage/core.entity_registry.bak-20261009140938` (3.4M) and `.storage/core.device_registry.20260810_040425.migration_backup` | Deleted in phase 1c, before the first backup |
| HA config-dir leftovers: `checkready.sh`, `influxdb-ignores.yaml`, `ui-panel-custom.yaml`, top-level `scripts.yaml`, `entities.yaml`, `python_scripts/` | Deleted in phase 1c. All six were tested unused (§8). The home copy carries every file forward on each release, so leftovers never clear on their own |
| `/home/asystem/<svc>/replaced/<run>/` from a snapshot replace | The next successful backup of that module |
| Databases left on an old TimescaleDB extension | Phase 1b, then every postgres release, §7 |
| New supervisor backup topics (`regressed`, `drill`) | Additive, so nothing is stranded. Any topic renamed during development is cleared with `mosquitto_pub -r -n`, per the repo rule |

### Residue check, the last gate of phase 7

Every line must print nothing:

```
grep -rn -E 'backup_pruned(_gfs)?\b|Prune disagreement|influxdb3_pruned_' src --include='*.py' --include='*.sh' | grep -v -E '/target/|/\.deps/'
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
