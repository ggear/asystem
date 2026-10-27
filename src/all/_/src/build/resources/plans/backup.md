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

Beside the archive, `<run>/manifest.json`, written by the wrapper from a new optional hook:

```
backup_fingerprinted   print one "<unit> <count>" line per unit of the backed-up state
```

| Module | Unit | Count |
|---|---|---|
| influxdb3 | `<table>/<day>` | rows |
| postgres, mariadb | `<database>.<table>` | rows (estimate from stats is fine, exact for small tables) |
| plex, letsencrypt, wrangle, zigbee2mqtt (`backup_files`) | include path | files and bytes, which the wrapper computes itself, so no hook is needed |

The manifest also records `kind` (full/delta), `parent` (the full a delta hangs off), `source_version` and `fingerprint`.
`parent` replaces the current inference from directory order, and every later step reads it.

### 2. Regression guard: a shrinking backup is not a good backup

After writing, the wrapper compares the new fingerprint with the newest *accepted* run's:

- Any unit present before and missing now, or a total drop beyond `<MODULE>_BACKUP_SHRINK_PERCENT` (default 20, `0`
  disables), marks the run **regressed**. Its archive is kept, since it is still the current state, but:
  - the run is published with a new backup state, `regressed`, through supervisor. That is a vocabulary change:
    `internal/metric/metric_schema.go` owns it, and the shell side mirrors `BACKUP_STATE_REGRESSED` under the existing
    parity test;
  - the last accepted full and its chain become the **anchor**, pinned by every pruner (primary, server-side store,
    secondary GFS, retire_home) until acknowledged;
  - acknowledging is `backup.sh --accept=<run>`, which marks the regressed run accepted and releases the anchor. It is
    for an intentional shrink, such as a retention change or a dropped table.
- For influxdb3 the first `full` after 26 Oct would have flagged the moment it was written, and the anchor would have
  kept `full-2026-10-19` indefinitely.

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

Window changes, measured against today's sizes (influxdb3 full 177M, growing about 20M a week):

| Module | Now | Proposed |
|---|---|---|
| influxdb3 | retain 7d, weekly 4, monthly 3 | retain 14d, weekly 8, monthly 12: about 2.5G on `/share/30`, and it is the estate's history |
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
| `merge` | yes, additively | `backup_fingerprinted`, `restore_staged`, `restore_merged` | Put back history the live service lost, keeping what it has written since |
| `drill` | no | `backup_fingerprinted`, `restore_staged` | Prove a backup restores and matches its own fingerprint |

A module that defines none of the new hooks keeps today's behaviour, and `merge` and `drill` refuse by name.

#### Invariants, and who enforces them

These are the rules the 2026-10-27 tests established (see *Recovering this incident*). The wrapper holds all but the
last two, so a module cannot skip one.

| Invariant | Enforced by | How |
|---|---|---|
| Scratch is read-only | wrapper | Fingerprints scratch straight after staging, before any other hook runs, then calls `restore_sealed` and fingerprints again. A sealed scratch whose fingerprint moved is a fault |
| Never restore into live and replay on top | wrapper | `merge` never calls `restore_applied`. `replace` refuses while live fingerprints any unit newer than the backup, unless `--force` |
| Verify after a restart, not after the write | wrapper | Restarts live through its compose before fingerprinting it again |
| Merge only what live lacks | wrapper | Diffs the two fingerprints and hands `restore_merged` only units where staged > live |
| Interrupted merges resume | wrapper | Records each finished unit in the restore run dir and skips it on a rerun |
| Rerun is harmless | contract | `restore_merged` must be idempotent: influxdb3 line protocol, `ON CONFLICT DO NOTHING`, `INSERT IGNORE` |
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
fingerprint S      scratch; compared to the manifest when the run has one (pre-manifest runs skip this)
restore_sealed     scratch now refuses writes
                   ── drill ends here: teardown, publish the drill state
fingerprint L      live
plan               units where S > L, printed; without --force stop here
restore_merged     per planned unit, progress recorded
restart live       stop/start through the module's compose
fingerprint L'     every planned unit must have L' >= S, else fault naming the short units
teardown           scratch container and data dir
```

| Module | `backup_fingerprinted` unit | `restore_sealed` | `restore_merged` |
|---|---|---|---|
| influxdb3 | `<table>/<day>` rows | re-run scratch with `--mode query` on the same data dir | Export the day from scratch as jsonl (`--format jsonl` emits blank lines, so skip them), convert to line protocol, and write to live's `/api/v3/write_lp?precision=nanosecond` in chunks. The conversion is a small Python script the hook pipes through, with tag escaping and null or empty tags left out of the series key |
| postgres | `<database>.<table>` rows | `default_transaction_read_only` on the scratch database | `pg_dump --data-only` per table from scratch into a staging schema in live, then `INSERT … SELECT … ON CONFLICT DO NOTHING`. Tables without a primary key are listed and skipped |
| mariadb | `<database>.<table>` rows | `SET GLOBAL read_only` on scratch | Same, with `INSERT IGNORE` |
| plex, letsencrypt, wrangle, zigbee2mqtt | include path (wrapper computes it) | none | None: file state has no meaningful merge, so `replace` and `drill` only |

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
`FAB_SKIP_DRILL=1` escape is there for large modules mid-iteration. Supervisor adds the same drill weekly against the
newest secondary full, which covers modules that rarely release.

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

## Recovering this incident

Use the secondary chain. It is complete and passes `gzip -t`:

```
/share/30/backup/influxdb3/2026-10-19_01-00-28   full   177M
/share/30/backup/influxdb3/2026-10-19_22-25-53   delta  4.5M
/share/30/backup/influxdb3/2026-10-20_01-00-08   delta  4.8M
/share/30/backup/influxdb3/2026-10-21_01-00-08   delta  7.5M
/share/30/backup/influxdb3/2026-10-22_01-00-08   delta   11M
```

A copy of the chain, pinned outside every pruner, is at `/share/30/tmp/influxdb3-restore-2026-10-22/`. Once step 5 of
the order of work lands, the recovery is one command, run bare to read the plan, then again with `--force`:

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

## Order of work

1. ~~Pin the five runs above outside every pruner, until the anchor exists.~~ Done, see above.
2. `commit=600` out of the `fstab` sources. Make the entrypoint quarantine-and-refuse change.
3. Manifest, chain-aware pruner and anchor in `container.py`. Raise influxdb3's window. Regenerate every enrolled module
   and read the generated `backup.sh` diffs.
4. Restore wrapper in `container.py`: chain resolution, `--source`, the flow and every wrapper-held invariant above,
   and `drill`. Wire drill into `install.sh`, then into supervisor weekly.
5. influxdb3 `backup_fingerprinted`, `restore_staged`, `restore_sealed` and `restore_merged`. Drill against the pinned
   chain, then run the merge to recover 2026-08-13 → 2026-10-22.
6. postgres and mariadb `restore_merged`.
7. Fold the durable rules into supervisor's `CLAUDE.md` Backup section, and delete this plan.
