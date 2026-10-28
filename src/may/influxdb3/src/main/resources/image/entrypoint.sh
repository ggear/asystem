#!/bin/bash
# Wrapper around the stock /usr/bin/entrypoint.sh that repairs damage left by an
# unclean shutdown before handing off to serve. Power loss leaves the newest
# PachaTree compactor checkpoints, gen0 snapshot manifests and WAL segments zero
# length, and serve then retries forever with "Failed to decompress V2 checkpoint:
# expected another byte", "Manifest too small for magic" or "WAL ... File too small
# for header". Empty files are moved to cv2/quarantine/<ts>/, never deleted. If that
# would leave no usable checkpoint or no usable manifest, serve would reset to an
# empty history and come up healthy, so the script refuses to start instead and the
# operator restores from backup.
set -euo pipefail

cluster_id="${INFLUXDB3_CLUSTER_ID:-}"
data_dir="${INFLUXDB3_DATA_DIR:-/asystem/mnt}"
checkpoint_dir="$data_dir/$cluster_id/cv2/checkpoints"
quarantine_dir="$data_dir/$cluster_id/cv2/quarantine/$(date +%Y-%m-%d_%H-%M-%S)"

log() { echo "entrypoint: $*"; }

quarantine() {
  mkdir -p "$quarantine_dir"
  mv -v "$1" "$quarantine_dir/"
}

refuse() {
  log "refusing to start, $1"
  log "restore from backup rather than serve an empty history, quarantined files are under '$quarantine_dir'"
  exit 1
}

if [[ "${1:-}" == serve || "${1:-}" == influxdb3 || "${1:-}" =~ ^- ]]; then
  if [[ -n "$cluster_id" && -d "$checkpoint_dir" ]]; then
    empties=$(find "$checkpoint_dir" -maxdepth 1 -type f -name '*.ptv2chk.lz4' -empty)
    if [[ -n "$empties" ]]; then
      log "quarantining empty compactor checkpoints under '$checkpoint_dir'"
      while IFS= read -r file; do quarantine "$file"; done <<<"$empties"
      if [[ -z "$(find "$checkpoint_dir" -maxdepth 1 -type f -name '*.ptv2chk.lz4' -size +0c -print -quit)" ]]; then
        refuse "every compactor checkpoint under '$checkpoint_dir' was empty"
      fi
    fi
  fi
  for snapshot_dir in "$data_dir"/*/pt_snapshots; do
    [[ -d "$snapshot_dir" ]] || continue
    empties=$(find "$snapshot_dir" -maxdepth 1 -type f -name '*.ptsnap' -empty)
    [[ -n "$empties" ]] || continue
    log "quarantining empty snapshot manifests under '$snapshot_dir'"
    while IFS= read -r file; do quarantine "$file"; done <<<"$empties"
    if [[ -z "$(find "$snapshot_dir" -maxdepth 1 -type f -name '*.ptsnap' -size +0c -print -quit)" ]]; then
      refuse "every snapshot manifest under '$snapshot_dir' was empty"
    fi
  done
  empties=$(find "$data_dir" -mindepth 4 -maxdepth 4 -type f -path '*/pt_wal/*.pt' -empty)
  if [[ -n "$empties" ]]; then
    log "quarantining empty WAL segments under '$data_dir/*/*/pt_wal'"
    while IFS= read -r file; do quarantine "$file"; done <<<"$empties"
  fi
fi

exec /usr/bin/entrypoint.sh "$@"
