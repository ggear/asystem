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
restore.sh [--mode=replace|merge|drill] [--from=<run>] [--file=<path>] [--force] [--no-backup]
```

The wrapper resolves the **chain**, not one artifact: the full named by the target run's manifest plus every delta up to
it, searched in order through primary, then secondary (`/share/<index>0/backup/<svc>`), then tertiary. `--file` stays for
an artifact off anywhere else. Each artifact is integrity checked before anything is staged.

| Mode | Touches live? | Needs | Use |
|---|---|---|---|
| `replace` | yes, stop or running per `RESTORE_SERVICE_STATE` | `restore_applied` (today's hook) | Wholesale rollback |
| `merge` | yes, additively | `restore_staged`, `restore_merged` | Put back history the live service lost, keeping what it has written since |
| `drill` | no | `restore_staged` | Prove a backup restores and matches its own fingerprint |

New optional hooks:

```
restore_staged    bring the resolved chain up in a scratch instance: container <module>_restore, data under
                  /home/asystem/<svc>/restore/<run>, bound to loopback on a free port, torn down by the wrapper on exit
restore_merged    copy from the scratch instance into live whatever live lacks, idempotently
```

After staging, the wrapper fingerprints the scratch instance with the module's `backup_fingerprinted` pointed at it,
and diffs that against the manifest. For `merge` it fingerprints live again after merging. Every unit must be
greater than or equal to the scratch instance's count for the merged range.

A module that defines neither hook keeps today's behaviour, and `--mode=merge` refuses by name.

| Module | `restore_merged` |
|---|---|
| influxdb3 | For each table, find days where live count < staged count (from the two fingerprints), export those days from scratch as line protocol (tags vs fields from `information_schema.columns`), and write them to live through `/api/v3/write_lp` in chunks. The same series key and timestamp overwrite, so a rerun is harmless |
| postgres | `pg_dump --data-only` per table from scratch into a staging schema in live, then `INSERT … SELECT … ON CONFLICT DO NOTHING`. Tables without a primary key are listed and skipped |
| mariadb | Same, with `INSERT IGNORE` |
| plex, letsencrypt, wrangle, zigbee2mqtt | None: file state has no meaningful merge, so `replace` and `drill` only |

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

This is the first real run of `--mode=merge` for influxdb3, and it is done by hand until the tooling exists. A copy of
the chain, pinned outside every pruner, is at `/share/30/tmp/influxdb3-restore-2026-10-22/`.

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

## Order of work

1. ~~Pin the five runs above outside every pruner, until the anchor exists.~~ Done, see above.
2. `commit=600` out of the `fstab` sources. Make the entrypoint quarantine-and-refuse change.
3. Manifest, chain-aware pruner and anchor in `container.py`. Raise influxdb3's window. Regenerate every enrolled module
   and read the generated `backup.sh` diffs.
4. Restore chain resolution and `drill`. Wire drill into `install.sh`, then into supervisor weekly.
5. influxdb3 `restore_staged` / `restore_merged`, then use it to recover 2026-08-13 → 2026-10-22.
6. postgres and mariadb `restore_merged`.
7. Fold the durable rules into supervisor's `CLAUDE.md` Backup section, and delete this plan.
