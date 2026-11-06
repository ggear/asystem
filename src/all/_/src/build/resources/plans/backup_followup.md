# Backup follow-up

The backup and restore plan closed on 2026-11-06. This holds the two things it left open. Delete this file when both are done.

## 1. First weekly drill, Monday 2026-11-09

**What it is.** On the first nightly run of each ISO week, secondary drills the sparse points it keeps (`drillSecondaryServices`). It has run in production only for catch-up drills (5 Nov). It has never selected a point because the week turned.

**Check, on Monday morning, on each of `macmini-mad`, `macmini-meg`, `macmini-may`, `macmini-max` and `raspbpi-jen`:**

```
ssh root@<host>
r=$(ls -1d /home/asystem/supervisor/backup/2026-11-09_01-* | head -1)
grep -E 'verified|faulting|WARN|ERROR|refused' $r/run.log
jq -c '{state,success_bool}' $r/status.json
for f in $r/stage/primary/service/*/status.json; do echo "$(basename $(dirname $f)) $(jq -c '{state,success_bool,drill_failed_bool}' $f)"; done
```

**Pass:**
- the run `state` is `success` and each service has `success_bool` true and no `drill_failed_bool`
- there are no `faulting`, `WARN`, `ERROR` or `refused` lines
- a `verified` line is expected only where a sparse point lacked a verdict (a point drills once, so there may be none, which is fine: every existing point was drilled on 5 Nov)
- `Fail BKP` reads 0 on every host's dashboard

**If it fails:** read `<share>/backup/<svc>/<run>/.meta/secondary/drill.json` and the failed service's `output.log`, then hand drill the same point: `/var/lib/asystem/install/<svc>/latest/restore.sh --mode=drill --from=<run> --runs=<share dir>`. A hand drill that passes while the stage failed means the fault is in the stage (`probe_util_backup_stage_drill.go`), not the backup.

**Known and fine:** postgres points 09-30, 10-18 and 10-25 carry failed verdicts because they predate the TimescaleDB update. They stay red in their own `drill.json` and the engine ignores them. 10-18 and 10-25 age out of the weekly tier around 17 to 23 Nov. 09-30 stays as September's monthly point for about a year unless deleted by hand from `/share/10/backup/postgres`.

## 2. influxdb3 live merge, deferred

**State.** `restore_merged` now writes through `docker exec` into the live container (`src/may/influxdb3/src/build/resources/restore.sh`). The code is in the tree and covered by stubbed unit tests only. It is not released, and it has never written to a real instance. Drills and replace are unaffected by it.

**Never test on production.** A real merge writes history into live, and the engine's final step restarts the module's compose. Test the hook alone against a throwaway instance.

**Steps, on `macmini-may`:**

1. Release influxdb3 so the host has the new `restore.sh` (its pre-install backup and drill run as usual).
2. Stage a sealed copy of the newest point and keep it:
   ```
   n=$(ls -1 /home/asystem/influxdb3/backup | grep ^2026 | tail -1)
   /var/lib/asystem/install/influxdb3/latest/restore.sh --mode=drill --from=$n --keep-scratch
   ```
   This leaves container `influxdb3_restore` holding the history, read-only.
3. Start an empty stand-in for live. It must never have been restored. Use a fresh data dir and the licence copy only:
   ```
   image=$(docker inspect influxdb3 --format '{{.Config.Image}}')
   d=/home/asystem/influxdb3/restore/mergetest
   mkdir -p $d/cluster_1 && cp /home/asystem/influxdb3/latest/cluster_1/trial_or_home_license $d/cluster_1/
   docker run -d --name influxdb3_mergetest --entrypoint influxdb3 --mount type=bind,source=$d,target=/asystem/mnt "$image" \
     serve --node-id node_1 --cluster-id cluster_1 --object-store file --data-dir /asystem/mnt --license-type home --without-auth --disable-telemetry-upload
   ```
   Never pass `--license-email`.
4. Merge one closed day into it by calling the hook directly, with the target name overridden. Pick a unit from the staged copy, for example `sensor__temperature/<a day well before today>`:
   ```
   S=/var/lib/asystem/install/influxdb3/latest/restore.sh
   INFLUXDB3_RESTORE_WRITE_TOKEN= bash -c ". $S; RESTORE_MODULE_NAME=influxdb3_mergetest; restore_merged 'sensor__temperature/<day>' influxdb3_restore"
   ```
5. Count the day in both and compare:
   ```
   q="SELECT count(*) FROM \"sensor__temperature\" WHERE time >= '<day>T00:00:00Z' AND time < '<day+1>T00:00:00Z'"
   docker exec influxdb3_restore   influxdb3 query --database home "$q"
   docker exec influxdb3_mergetest influxdb3 query --database home "$q"
   ```
6. Run step 4 a second time and count again.
7. Clean up:
   ```
   docker rm -f influxdb3_restore influxdb3_mergetest
   rm -rf /home/asystem/influxdb3/restore/*
   ```

**Pass:**
- step 4 exits 0 and prints no `returned [` fault
- the two counts in step 5 are equal and non-zero
- the count is unchanged after step 6, so the rewrite is idempotent
- production `influxdb3` is untouched: still `healthy`, its row counts unchanged

**If it fails:** a non-204 code names the status in the fault line. Check `docker exec influxdb3_mergetest curl -s http://127.0.0.1:8181/health` first. The stand-in has no auth, so a 401 would mean the wrong container was written to, which must never be live.

**What this does not prove.** The engine's whole merge flow (plan, per-unit progress, live restart, post-restart fingerprint) and tags and nanosecond precision across every table are not covered. The 28 Oct production merge proved that flow on the old bash version. To prove it on the Go engine, a whole-flow run needs a way to point the engine at the stand-in without restarting the real compose, which does not exist today. Decide whether that is worth building only if a real merge ever looks likely.

## Done when

Section 1 passes on all five hosts, and section 2 passes or is dropped by decision. Then delete this file.
