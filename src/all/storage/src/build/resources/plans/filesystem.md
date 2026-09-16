# filesystem

Standardise the servers' root filesystem on a single btrfs pool with subvolumes, replacing the
fixed LVM+ext4 volumes on `max`, `may` and `meg` with the layout `mad` already runs. **planned** —
nothing here is in the repo, and none of it is automated; this is a per-host rebuild procedure.
Status vocabulary: **built** is in the repo today, **planned** is not, **ruled out** was considered
and rejected on the evidence recorded beside it, **measured** is a number taken off a host on
2026-09-16 rather than reasoned about.

Read *Why* and *Subvolumes do not constrain* first. The power-loss section exists because it is the
obvious objection and the evidence points the other way; it ends by naming the two risks that are
real, neither of which is the filesystem.

---

## Current state, measured

| Host | OS / kernel | Root disk | Layout |
|---|---|---|---|
| `mad` | Fedora Asahi 42 / 6.14 | 466G NVMe | **btrfs**, one pool, subvols `root`/`home`/`var`, `compress=zstd:1` |
| `max` | Fedora 42 Server / 6.16 | 1.8T NVMe | LVM+ext4 — root 25G, var 30G, tmp 1G, home 335G, `share_06` 1.4T |
| `may` | Debian 12 / **6.1** | 3.6T NVMe | LVM+ext4 — root 25G, var 30G, tmp 20G, home 412G, `share_04` 3.1T |
| `meg` | Debian 12 / **6.1** | 1.8T NVMe | LVM+ext4 — same shape, `share_01` 1.3T |
| `jen` | Debian 12 / 6.1 | 119G USB flash | single ext4, no LVM |

Three distros and three kernel lines across four servers. **Standardising the distro is the larger
win than standardising the filesystem** and should be taken at the same time, since a conversion is
a reinstall either way: Debian 12 goes to trixie (6.12) or the host moves to Fedora.

## Why

The LVM layout is already failing in the predicted way — capacity is stranded behind boundaries
chosen once at install time, while the boundaries that matter run tight. Measured:

| Host | `/` | `/var` | `/home` | Stranded |
|---|---|---|---|---|
| `max` | 7.1G of 25G | 13G of 30G | **773M of 329G** | ~328G idle, 17G free on `/` |
| `may` | 6.3G of 25G | 14G of 30G | 1.8G of 405G | ~403G idle; `/tmp` 160K of 20G |
| `meg` | **14G of 25G (61%, 9.2G free)** | 12G of 30G | 31G of 405G | ~374G idle |
| `mad` | — one 395G pool, 77G used (20%) — | | | none — no boundary can be hit |

`meg` is the live case: `/` at 61% with 354G sitting idle in `/home` and 42G unallocated in the VG.
The cause is `/root` (3.4G) and `/media` (4.8G) — junk outside both `/home` and `/var`, on the one
volume with no room to take it.

**The immediate fix is an `lvextend`, not a migration.** `lvextend -r -L +20G /dev/macmini-meg-vg/root`
takes five minutes from the free VG space. Do it independently of everything below; do not let a
filesystem decision gate it.

## Subvolumes do not constrain — that is the point

The framing that prompted this plan was "use btrfs to constrain `var`/`tmp`/`home`/`shares`".
Btrfs subvolumes do the **opposite**: they all draw from one free pool with no limits. That is the
property worth having, but it is un-constraining, not constraining.

- **`qgroups` — ruled out.** They are the only way a subvolume gets a real cap, and they are a
  known performance cliff: every extent is accounted at commit time and it degrades badly once
  snapshots are involved. The estate takes snapshots on `/backup` already.
- **Where a hard limit is genuinely wanted, keep a partition boundary.** This is why the big shares
  stay outside the system pool — a runaway download filling `/share` must not be able to fill `/`,
  which is the exact failure being escaped.

## What btrfs buys this estate

- **The stranded-capacity problem disappears permanently.** No sizing guess survives contact with
  five years of use; a single pool never has to make one.
- **Checksums against the existing scrub discipline.** `backup.sh` already runs `btrfs scrub`
  monthly on `/backup` on every host, so extending it to the system pool is operationally free and
  reports *which file* is corrupt rather than silently serving bad bytes. Single-device metadata is
  `DUP` (confirmed on `mad`), so metadata corruption self-heals; data is `single`, so detect-only.
- **Compression.** `mad` runs `zstd:1` pool-wide; on `/var` — docker images and logs — that is real.
- **Snapshots could retire the release copy** — `install.sh` does a full physical
  `cp --reflink=never` of the previous `${SERVICE_HOME}` on every release (~19 GB for plex on
  `mad`). A read-only pre-release subvolume snapshot is instant and gives rollback. **Not part of
  this plan**: the reflink ban exists for a measured reason (22 853 extents in a 467 MB postgres
  relation) and a snapshot reintroduces extent sharing, so it needs its own design.

## What it costs

- **`chattr +C` starts firing estate-wide.** It is currently a no-op on `max`/`may`/`meg` because
  they are ext4. After conversion the postgres, influxdb3 and plex data become nodatacow — correct,
  already implemented, and it carries a trade worth stating: **nodatacow also disables checksums**,
  so the scrub benefit covers everything *except* the databases.
- **Docker needs the nocow pattern.** `mad` already does this — `Docker Root Dir:
  /var/lib/docker_nocow` with overlay2 on top. Replicate it; `/var/lib/docker` must not sit CoW.
- **ENOSPC with free space showing in `df`.** Allocated-but-unused chunks are the classic btrfs
  surprise. `mad` is healthy today (87.8G data chunks at 86.6% used against 302G unallocated) but it
  is a state to know about, cleared with `btrfs balance -dusage=50`.
- **The recovery toolbox is less forgiving.** `fsck.ext4 -y` will bulldoze an ext4 back to
  mountable; `btrfs check --repair` is documented as dangerous. Modern btrfs recovers itself via
  backup tree roots (`-o usebackuproot`), and `mad`'s record below is evidence that it does — but
  the tail risk lands somewhere worse, and the verified nightly backups are the mitigation.

## Target layout

Match `mad` so there is one layout estate-wide.

```
nvme0n1p1  vfat   /boot/efi
nvme0n1p2  ext4   /boot                     kept off btrfs, simpler bootloader story
nvme0n1p3  PV     existing VG, kept          see "Keep LVM on max/may/meg"
  delete     root, var, tmp, home, swap LVs  ~490G freed
  create     system 200G -> mkfs.btrfs       compress=zstd:1, noatime
               subvol root -> /
               subvol home -> /home
               subvol var  -> /var
               subvol tmp  -> /tmp
  KEEP       share_NN LV                     untouched, never reformatted
```

- **200G is generous.** Current system usage is ~21G (`max`), ~22G (`may`), ~57G (`meg`), 77G
  (`mad`).
- **`/tmp` as a subvolume, not tmpfs.** `mad` runs a 2G tmpfs; a subvolume costs nothing and removes
  the failure the root `CLAUDE.md` already flags — a mirror into tmpfs consuming RAM and OOMing the
  host.
- **Shares stay ext4.** They are write-once media; `mad`'s ext4 shares run 1 extent per 100 MB, so
  btrfs buys them nothing and converting 12 TB is days of I/O for no gain.

### Keep LVM on max/may/meg — ruled out dropping it

The first version of this plan said drop LVM and use plain partitions. That is wrong here, because
on all three hosts one share is a logical volume **inside the VG being dismantled**:

| Host | Share | LV | Size / used |
|---|---|---|---|
| `max` | `/share/20` | `fedora_macmini-max/share_06` | 1.4T / 716G |
| `may` | `/share/30` | `macmini-may-vg/share_04` | 3.1T / 1.8T |
| `meg` | `/share/40` | `macmini-meg-vg/share_01` | 1.3T / 1.1T |

Getting to plain partitions means `pvmove`ing the share LV to the end of the PV, `pvresize`, then
shrinking the partition — fiddly, risky, and it buys nothing. **LVM under a single-pool btrfs is a
device-mapper layer with negligible overhead**, and it preserves exactly the system/share boundary
that is wanted anyway. Deleting only the system LVs and creating one `system` LV for btrfs moves
zero share data.

### Six of nine share volumes need nothing at all

They are on their own physical disks, so repartitioning `nvme0n1` does not reach them: `max`
`/share/21` (`sda1`, 279G); `may` `/share/31` (`sda1`, 2.2T) and `/share/32` (`sdb1`, 331G); `meg`
`/share/41` (`sda1`, 2.8T) and `/share/42` (`sdb1`, 315G). `mad`'s three are on `sda`/`sdb`/`sdc`
and `mad` is not being converted.

### Guardrails for the LV surgery

The danger is not the plan, it is an installer mis-click reformatting the wrong LV.

1. **`vgcfgbackup` first** — `vgcfgrestore` recovers an LV deleted by mistake, provided nothing has
   written over the extents yet.
2. **Set the share LV read-only for the duration** — `lvchange --permission r /dev/<vg>/share_NN`,
   so a stray format fails instead of succeeding. `--permission rw` afterwards.
3. **Do the surgery from a live USB, before the installer.** Delete the system LVs, create and
   `mkfs.btrfs` the new one with its subvolumes, then have the installer only *assign mountpoints*
   — never format.
4. **Leave `/backup` disconnected during the install.** It is `noauto` and normally powered down, so
   it will not be touched, but do not give an installer the chance to see it as a target.
5. **Normalise the share fstab entries to `UUID=`.** `max` uses `/dev/fedora_macmini-max/share_06`
   and `may`/`meg` use `/dev/mapper/…`; those break if a reinstall renames the VG (Debian uses
   `<host>-vg`, Fedora `fedora_<host>`). The filesystem UUID survives everything, and the other
   shares already use `PARTLABEL=share_NN`.
6. **`btrfs-convert` from ext4 — ruled out.** It exists and is explicitly not recommended for a root
   filesystem. This is a rebuild.

### The restore path exists and is verified nightly

Every host completed a `tertiary` mirror at 01:00 on 2026-09-16, and the sizes reconcile against the
local shares — `max` 1.0 TiB on `/backup` against ~995G local, `may` 4.2 TiB against ~4.3T, `meg`
4.1 TiB against ~4.2T. `tertiary` mirrors each locally-owned share **whole**, not just the backups,
so a wipe-and-restore is possible and is local rather than over the network.

Treat it as the net, not the plan: restoring 1.8T at the measured 100–205 MB/s is 2.5–5 hours per
host, for no benefit over leaving the LV alone. Run `abackups start` by hand the evening before each
rebuild so the mirror is same-day.

## Power loss is not the objection it looks like

The estate has no UPS and takes unclean shutdowns. Every part of this was checked rather than
argued.

**`mad`'s record is clean.** It has run btrfs across those power cuts:

```
[/dev/nvme0n1p6].write_io_errs     0
[/dev/nvme0n1p6].read_io_errs      0
[/dev/nvme0n1p6].flush_io_errs     0
[/dev/nvme0n1p6].corruption_errs   0
[/dev/nvme0n1p6].generation_errs   0
```

Zero on every counter, 10 boots recorded, 69 days uptime. The only btrfs warnings in the journal —
all 20 — are one repeated `read-write for sector size 4096 with page size 16384 is experimental`
against `sdd1`, the `/backup` disk. That is an Asahi 16K-page quirk, not corruption, and the x86
hosts will not produce it.

**Btrfs is structurally better than ext4 here, not worse.** CoW means a block is never
half-overwritten — the old version or the new one, never a mix — the superblock flip is atomic, and
recovery rolls back to the last commit with no fsck on boot. ext4 `data=ordered` journals metadata
only, so a correctly-structured file containing torn or stale data blocks is precisely the ext4
power-loss failure mode, and it is the one btrfs does not have. Single-device btrfs also defaults to
`Metadata,DUP` — two copies it self-heals from — against ext4's one. The reputation btrfs carries on
this is the **RAID5/6 write hole** (single-device here, so irrelevant) and **pre-4.x kernel bugs**
(the estate is on 6.1–6.16).

**But `chattr +C` turns that off for exactly the databases.** nodatacow means in-place overwrites
and no checksums, so postgres and influxdb3 data files carry the same torn-write exposure as ext4 —
and btrfs cannot even detect it, having no checksum to compare. The filesystem contributes nothing
there, so the safety must come from the database, and it does. Measured on `mad`:

```
full_page_writes   = on        exists precisely to survive torn pages
fsync              = on
synchronous_commit = on
wal_sync_method    = fdatasync
data_checksums     = on
```

`full_page_writes` writes whole pages into WAL after each checkpoint so a torn page is reconstructed
on recovery, and it works identically on ext4 and btrfs. InfluxDB 3 is structurally safer again —
WAL plus write-once, then-immutable parquet, which is the ideal shape for CoW.

### The two risks that are real, and neither is btrfs

1. **`commit=600` on `max`/`may`/`meg`** — `/`, `/home`, `/var` and `/tmp` are all mounted with a
   **ten-minute** journal commit interval against a 5-second default. fsync'd data is unaffected, so
   the databases are fine, but everything not fsync'd carries up to ten minutes of exposure on a
   power cut: docker state, logs, config, anything a script writes. That is a far larger
   unclean-shutdown risk than the filesystem choice, it is live today on ext4, and the write
   amplification it saves is negligible on NVMe. `mad`'s btrfs sets no `commit=` and runs the 30s
   default. **Drop it to the default whether or not the conversion happens.**
2. **There is no UPS on any host** — no `upsc`, no `apcaccess`, nothing on USB, checked on all four.
   A small UPS with NUT triggering a clean shutdown at low battery deletes the entire class of risk
   and makes this section moot. Against nightly backups, monthly scrubs, per-metric monitoring and a
   bounded-stop release path, it is the one missing layer and the cheapest one left.

## Sequencing

1. **Now, independent of everything else** — `lvextend` `meg`'s root from the free VG space, and
   clear `/root` and `/media`. Drop `commit=600` on all three. Buy a UPS.
2. **At the next OS reinstall of any server** — build it to the layout above. Do not schedule three
   rebuilds; take each host as it comes up for a distro move it needs anyway.
3. **Order when it happens** — `may`, then `meg`, then `max`. `max` holds influxdb3, so its outage
   costs the estate's metrics history for the window.
4. **`jen` stays ext4 — ruled out converting it.** It boots from a 119G USB flash drive. Btrfs
   metadata write amplification on cheap flash is a real cost with none of the benefits, there is no
   LVM there to escape from, and `supervisor`'s own drive-wear metric already excludes flash drives.

## Consequences for the rest of the repo

- **`supervisor`'s `used_home_space` changes meaning.** It picks the deepest non-share mount holding
  `/home/asystem`; on a shared pool every subvolume reports the same pool figures (`mad` reports
  395G/77G for `/`, `/home` and `/var` alike). That is the more useful number — the pool is what can
  actually fill — but it is a silent discontinuity in the InfluxDB series, the same class as the
  sensor-rescaling note in `src/all/supervisor/CLAUDE.md`. Nothing is renamed, so no
  `database_archive_measures` entry is needed and no topic moves.
- **`backup_usage`'s btrfs path newly engages on `max`/`may`/`meg`**, including the
  `BACKUP_USAGE_UNIDENTIFIED` fallback that `mad` already exercises for a btrfs path the container
  did not mount itself.
- **`install.sh`'s `chattr +C` stops being a no-op on those hosts**, so each service's next release
  becomes a full defragmentation of its data — measured on `mad`'s postgres as 98 105 extents to 58
  across 57 files of 3570 MB.
