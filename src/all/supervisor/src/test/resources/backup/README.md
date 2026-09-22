# Backup fixtures

Real tool output captured from the estate on 2026-09-22, for the parser tests in
`src/build/resources/plans/goimpl.md`. **Nothing here is synthesised** — that is the point of the
directory. A parser tested against hand-written input passes its tests and fails on a real disk, and
three of the cases below are ones nobody would have thought to write.

Every `.txt` file opens with the `$ command` that produced it and closes with its `[exit N]`, because
for `smartctl` and `btrfs` the exit status is part of the contract and reading it is what tells an
unreadable drive from one with no SMART at all.

Captured read-only. `btrfs scrub start`, `btrfs balance start` and `btrfs device stats -z` all mutate
and were not run.

## Provenance and what each case proves

| File | Host | Proves |
|---|---|---|
| `btrfs/scrub-status-never-scrubbed.txt` | mad `/` | `no stats available` — renders **no percentage at all**, so the `(NN.NN%)` regex finds nothing |
| `btrfs/scrub-status-raw-never-scrubbed.txt` | mad `/` | the `-R` counter block, every key at zero |
| `btrfs/scrub-status-unmounted.txt` | max `/backup` | `ERROR: not a btrfs filesystem` |
| `btrfs/filesystem-show-unmounted.txt` | max `/backup` | `ERROR: not a valid btrfs filesystem` — the `backup_usage` fallback-to-`df` branch |
| `btrfs/filesystem-show-single-device.txt` | mad `/` | the `uuid:` line `backup_usage` greps for |
| `btrfs/device-stats-clean.txt` | mad `/` | the `[/dev/x].key value` shape `backup_device_counter` sums |
| `btrfs/subvolume-show-toplevel.txt` | mad `/` | a real subvolume, for the tertiary snapshot check |
| `btrfs/subvolume-show-unmounted.txt` | max | the not-a-subvolume refusal |
| `btrfs/scrub-status-persisted-finished-resumed.txt` | may | **a completed 4.6 TB scrub that was resumed mid-pass** — `t_resumed`, `finished:1`, real magnitudes |
| `btrfs/scrub-status-persisted-finished.txt` | mad | the same, single pass |
| `mounts/findmnt-btrfs-host.txt` | mad | the one host with a btrfs root, three mounts on one device |
| `mounts/findmnt-ext4-host.txt` | max | the ext4 hosts, where `/backup` is the only btrfs |
| `mounts/fstab-server-btrfs.txt` | mad | `/backup` + `/share/*` declarations, server form |
| `mounts/fstab-edge.txt` | jen | an edge host with no `/backup` at all |
| `mounts/df-unmounted-backup.txt` | max | `df` of an unmounted `/backup` **succeeds**, reporting the underlying root |
| `mounts/meminfo-flush.txt` | mad | `Dirty:`/`Writeback:` for `backup_flushing` |
| `rsync/output-tertiary-mirror.log` | meg | a real mirror with creations **and deletions**, thousands-separated |
| `rsync/output-secondary-promote.log` | mad | a real promotion, multiple services |
| `rsync/output-secondary-edge.log` | jen | the smallest real case |
| `kernel/dmesg-filtered.txt` | mad | what `backup_scrub`'s grep actually matches on a live host |

### smartctl — eleven distinct outcomes, one file each

| File | Proves |
|---|---|
| `nvme-internal-ok.json` | `APPLE SSD AP0512Z`, NVMe health log, `percentage_used` present |
| `usb-bridge-sntrealtek-ok.json` | `-d sntrealtek` names the real disk behind mad's bridge — `Lexar SSD NM790 4TB`, with data |
| `usb-bridge-sat-lies-exit4.json` | **`-d sat` against the same bridge exits 4, prints a model, and carries no attribute table** — the first-match-wins trap |
| `sata-attr-241-and-246.json` | meg's Kingston carries **both** 241 and 246, which is why 241 must win |
| `sata-attr-246-only.json` | `CT4000MX500SSD1` reporting 246 as `Unknown_Attribute` on this userland |
| `scsi-inquiry-split-model.json` | `-d scsi` renders `CT4000MX 500SSD1` **with a space** — the 8/16-byte INQUIRY field split |
| `scsi-no-smart-support.json` | a clean exit with no support and no messages — genuinely no SMART |
| `wrong-kind-nvme-exit2.json` | wrong `-d` for the transport, exit 2 |
| `wrong-kind-sat-exit2.json` | the same the other way round |
| `usb-flash-drive.json` | jen's flash drive, which also reports `queue/rotational=1` |

### documents — one per kind and state

`run-{success,stopped}`, `stage-success-secondary`, `stage-stopped-tertiary`,
`service-{success,skipped}`, `scrub-{success,stopped,skipped}`. Real documents from real runs, so the
port's marshal can be asserted against them field for field.

## Two live defects this capture found — fixed

Both were real defects rather than quirks, so both were **fixed in `backup.sh` before the port**,
as the two declared exceptions to its exact-reimplementation rule. Fixing them in the shell first is
what stops the port inheriting a bug and the blame for it. `documents/scrub-success.json` is kept as
the evidence of the old behaviour, so it now records what the fix corrected.

- **A completed scrub recorded `progress_perc: 0`.** `documents/scrub-success.json` is a genuine
  4.4 TB success reporting zero percent, and the operator saw
  `scrub [success] at [ 0] percent having scrubbed [4416965] MiB`. A finished or aborted
  `btrfs scrub status` stops printing `(NN.NN%)`, so the final reading parses as zero; the
  `[ "${progress%%.*}" -eq 0 ] && progress="${reached:-0}"` guard existed to catch exactly this and
  could not, because `reached` was captured **after** the final zero reading rather than before it.
  `reached` is now declared with the other locals and updated inside the loop, before the finishing
  read can overwrite it, and the in-loop log line and document are rendered from it — so a run also
  stops logging a spurious `0 percent` on its last tick.
- **The percentage legitimately exceeds 100.** The same run logged `100.08` then `100.15`, because
  btrfs rates a *resumed* pass against the whole filesystem. It is now clamped in
  `backup_scrub_reading`, at the source, so the log line and the `progress_perc` field agree and
  `backup_percent` stays a pure padder — the rule that one padder per unit carries no policy.

Both fixes were verified to bite: reverted, the tests fail with `0 != 98.44` and `'100.15' != '100'`,
which is precisely what production produced.

## Capturing a running scrub

`btrfs scrub status` renders differently while a pass is running, and that rendering only exists
while `/backup` is mounted — which it is not between runs, because the reaper powers the disk down.
The `scrub-status-*running*` files here were taken on max on 2026-09-22 by resuming its already
`aborted` pass for 40 seconds and cancelling it, which returned the disk to the same `aborted` state
having completed ~6.8 GB more of the scrub. Do it the same way if they ever need retaking, and only
on a volume whose pass is already aborted, so the resume is work the next run would have done anyway.

The pair taken 20 seconds apart is worth keeping together: `data_bytes_scrubbed` moved 3.47 GB
between them — 3.23 GiB, about 165 MiB/s — while btrfs's own `Rate:` field read 28.25 MiB/s, a
cumulative average over the whole 9h55m pass. That is the live evidence for why `backup_sampled` rates a sliding window
instead of reading `Rate:`.
