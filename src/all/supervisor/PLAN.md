# PLAN — Used SYS, Used SHR and Fail SHR

Implementation plan for the three stubbed host metrics `MetricHostUsedSystemSpace`,
`MetricHostUsedShareSpace` and `MetricHostFailedShares`, all of which currently
`return 0, nil` in `probe_host.go`.

## Decisions taken

| Question | Decision |
|---|---|
| Used SYS value | **max** used share across deduped standard filesystems |
| Used SHR value | **sum(used) / sum(total)** across locally mounted shares, one number |
| Used SHR scope | local shares only — remote shares are reported by whichever host owns them |
| Fail SHR scope | **all** shares, local and remote |
| Fail SHR cadence | the **cache period** |

Used SYS takes the max because the aggregate hides the failure it exists to catch:
on `max` the four filesystems sum to 4.8% while `/var` sits at 38%, and a full `/var`
would still read only ~13% against a `<= 90` predicate. Used SHR takes the sum because
a host's shares are one pool of bytes, not four independent risks.

## Phase 1 — make `cache-period` usable

`makePeriods` calls `toDuration(cachePeriod, time.Hour, "cache")`, which rejects any
value that is not a whole number of hours — `-C 5m` is an error today and the floor is
one hour. `Periods.CacheHours` is currently read by nothing, so changing its unit has no
blast radius.

1. `cmd/cmd.go` — `toDuration(cachePeriod, time.Minute, "cache")`, yielding `cacheMins`.
2. `internal/config/config.go` — rename `Periods.CacheHours` to `CacheMins`.
3. `internal/engine/engine.go` — the `CacheHours: 0` literal in `RunAllProbesOnce`.
4. `internal/config/config.go` — add `DefaultCachePeriod = "1h"` beside `DefaultTrendPeriod`,
   and have both `--cache-period` flags take their default from it (currently the literal
   `"1h"` appears in `cmd_serve.go` and `cmd_watch.go`).
5. `internal/config/config.go` — add `CacheWindow(cacheMins int) time.Duration` mirroring
   `TrendWindow`, with a `parsedCachePeriod()` fallback for the disabled case.
6. Test `TestConfig_CacheWindow` alongside `TestConfig_TrendWindow`.

## Phase 2 — `internal/probe/probe_mounts.go`

A `mountSet` cached per root, in the shape of `probe_logs.go` and `probe_sensors.go`:
`loadMounts(mount string, window time.Duration) *mountSet`, a package-level cache keyed by
root, and `resetMounts()` for tests.

### Why the refresh is asynchronous

The cost is not CPU — four system filesystems plus twelve shares is ~16 `statfs` calls,
microseconds each on healthy mounts. The hazard is that `statfs` and `stat` on a hung CIFS
mount **block indefinitely and cannot be interrupted**; there is no timeout parameter. A
synchronous refresh, even a TTL-gated one like `probe_install.go` uses, would park the poll
goroutine and stall every metric on the host, so one dead share on `meg` would blank `mad`'s
dashboard. Therefore:

- reads return the current snapshot immediately and never block;
- a read older than the window spawns a refresh goroutine, unless one is already running;
- each mount is measured under `mountDeadline` (5s); a timeout marks that mount failed;
- a mount with an outstanding probe is skipped by later refreshes, so hung mounts cannot
  accumulate goroutines.

Before the first snapshot lands, the metric functions return **`errProbeWarmingUp`**, which
`runMetricCacheTask` already excludes from `errored` — so a starting host reads not-ok rather
than falsely green or falsely red.

### Types

```go
type mountUsage struct {
    device     string
    mountpoint string
    fstype     string
    share      bool
    remote     bool
    total      uint64
    used       uint64
    mounted    bool
}

type mountSnapshot struct {
    taken  time.Time
    mounts []mountUsage
    valid  bool
}
```

### Discovery and classification

Parse `<root>/proc/mounts` directly, the same precedent as `probe_sensors.go` reading `/sys`.

| Class | Rule |
|---|---|
| share | mountpoint under `/share/`, matching `SHARE_ROOT` in media's `.env_media` |
| share, remote | fstype in `cifs`, `nfs`, `nfs4`, `smb3` |
| share, local | any other share fstype |
| system | not a share, fstype not in the pseudo deny-list, mountpoint not under `/boot` |

The pseudo deny-list is `tmpfs`, `devtmpfs`, `devpts`, `overlay`, `squashfs`, `autofs`,
`proc`, `sysfs`, `securityfs`, `debugfs`, `tracefs`, `configfs`, `pstore`, `bpf`, `mqueue`,
`hugetlbfs`, `cgroup`, `cgroup2` and any `fuse.*`.

Local versus remote keys off **fstype**, not `.env_media`'s `grep ext4`: `max`'s share sits on
LVM and may be xfs, and "not a network filesystem" is the robust form of the same test with no
fstab parsing.

**Dedupe system filesystems by device.** `mad` mounts `/dev/nvme0n1p6` at `/`, `/home` and
`/var`; undeduped its totals treble. Keep the shortest mountpoint per device. Shares are not
deduped — each is its own filesystem.

### Path rooting

Every mountpoint read out of `<root>/proc/mounts` is a **host** path and must be re-prefixed
with the root before use: the container statfs's `<root>/share/20`, not `/share/20`, and tests
`<root>/share/20/media`. `logRoots`-style two-roots-as-bases applies — `$SUPERVISOR_MOUNT`
first, then bare.

## Phase 3 — wire the metrics

`probe_host.go`, each reading `loadMounts(config.Load(p.configPath).Mount(), config.CacheWindow(p.periods.CacheMins))`:

- `usedSystemSpace()` — max of `used/total` over the deduped system mounts.
- `usedShareSpace()` — `sum(used) / sum(total)` over local shares.
- `failedShares()` — `failed / total * 100` over all shares, where a share fails when it is
  absent from `/proc/mounts` or `<mountpoint>/media` is not a directory. Presence is free and
  never blocks, catching an unmounted share; the `-d` stat is what catches a mounted-but-dead
  CIFS share, and is the call that needs the deadline.

Predicates are unchanged — `<= 90` / `<= 80` for the two usage metrics, `== 0` / `== 0` for
Fail SHR, which gives red while broken, sticky yellow for the rest of the trend window after
recovery, then green.

`metric_build.go` — set `MetricHostFailedShares.unit` to `"%"` (currently `""` while the
display box already renders `%`, the mismatch `Fail LOG` had) and refresh the three
descriptions to state max, sum and the share-of-shares respectively.

## Phase 4 — tests

`probe_mounts_test.go`, with a `writeMountTree` helper in the shape of `writeLogTree` and
`writeSensorTree`: a temp root holding `proc/mounts` plus the share directories, and an
injectable statfs so usage figures are fixtures rather than the dev machine's real disks.

Table tests for: classification of the three real host layouts in this plan's source data
(`mad`, `max`, `jen`); device dedupe collapsing `mad`'s three mounts to one; max versus sum
arithmetic; a share missing `media/` counting as failed; a remote share counting for Fail SHR
but not Used SHR; and a probe exceeding `mountDeadline` marking that mount failed without
blocking the read.

## Phase 5 — regenerate and document

1. `fab generate` — the unit and description changes rewrite the influxdb3 model leaf and
   the describe/verify scripts.
2. Module `CLAUDE.md` — a `probe_mounts.go` package note covering the async refresher and
   why it is not the `probe_install.go` TTL shape, the classification table, the device
   dedupe, the max/sum split and its reason, and the path-rooting rule.
