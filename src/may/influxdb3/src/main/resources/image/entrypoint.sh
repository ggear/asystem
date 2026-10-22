#!/bin/bash
# Wrapper around the stock /usr/bin/entrypoint.sh that repairs damage left by an
# unclean shutdown (power loss, or SIGKILL after the docker stop grace period)
# before handing off to serve. Three stages:
#   1. Delete empty/truncated (<12 byte) WAL files. Replay skips them ("WAL file
#      too small"), but the writer later collides with the same numbered file and
#      aborts with "another process has written to the WAL ahead of this one".
#   2. Clear a stale ingest registration. node_<n> stays marked as the live
#      ingester, so serve aborts with "... still running in another process". A
#      query-mode server does not claim the ingest role, so it starts despite the
#      stale registration and can mark the node stopped via `stop node`.
#   3. If that recovery server still cannot load the WAL, list the partially
#      written WAL files it rejected and print the `rm` commands to remove them.
#      These are left for an operator: unlike stage 1 they may hold partial data.
# Those stages target the Parquet engine layout. For the PachaTree layout, empty
# compactor checkpoints, gen0 snapshot manifests and WAL segments are deleted
# first: power loss leaves the newest ones zero length, and serve then retries
# forever with "Failed to decompress V2 checkpoint: expected another byte",
# "Manifest too small for magic" or "WAL ... File too small for header".
set -euo pipefail

node_id="${INFLUXDB3_NODE_ID:-}"
cluster_id="${INFLUXDB3_CLUSTER_ID:-}"
data_dir="${INFLUXDB3_DATA_DIR:-/asystem/mnt}"
wal_dir="$data_dir/$node_id/wal"
checkpoint_dir="$data_dir/$cluster_id/cv2/checkpoints"
recover_addr="127.0.0.1:18181"
recover_log="/tmp/recover.log"

log() { echo "entrypoint: $*"; }

if [[ "${1:-}" == serve || "${1:-}" == influxdb3 || "${1:-}" =~ ^- ]]; then
  if [[ -n "$cluster_id" && -d "$checkpoint_dir" ]]; then
    log "removing empty compactor checkpoints under '$checkpoint_dir'"
    find "$checkpoint_dir" -maxdepth 1 -type f -name '*.ptv2chk.lz4' -empty -print -delete || true
  fi
  for snapshot_dir in "$data_dir"/*/pt_snapshots; do
    [[ -d "$snapshot_dir" ]] || continue
    log "removing empty snapshot manifests under '$snapshot_dir'"
    find "$snapshot_dir" -maxdepth 1 -type f -name '*.ptsnap' -empty -print -delete || true
  done
  log "removing empty WAL segments under '$data_dir/*/*/pt_wal'"
  find "$data_dir" -mindepth 4 -maxdepth 4 -type f -path '*/pt_wal/*.pt' -empty -print -delete || true
fi

if [[ ("${1:-}" == serve || "${1:-}" == influxdb3 || "${1:-}" =~ ^-) &&
  -n "$node_id" && -d "$data_dir/$node_id" ]]; then

  # Stage 1: drop empty/truncated WAL files (safe, they carry no records).
  if [[ -d "$wal_dir" ]]; then
    log "stage 1: removing empty/truncated WAL files under '$wal_dir'"
    find "$wal_dir" -maxdepth 1 -type f -name '*.wal' -size -12c -print -delete || true
  fi

  # Stage 2: clear a stale ingest registration using a throwaway query-mode
  # server, bound to loopback so it stays invisible to the bootstrap health gate.
  log "stage 2: clearing any stale ingest registration for node '$node_id'"
  influxdb3 serve --mode query --http-bind "$recover_addr" >"$recover_log" 2>&1 &
  recover_pid=$!
  healthy=""
  for _ in $(seq 1 30); do
    if [[ "$(curl -fsS "http://${recover_addr}/health" \
      -H "Authorization: Bearer ${INFLUXDB3_AUTH_TOKEN:-}" 2>/dev/null)" == "OK" ]]; then
      healthy=1
      break
    fi
    kill -0 "$recover_pid" 2>/dev/null || break
    sleep 1
  done
  if [[ -n "$healthy" ]]; then
    influxdb3 stop node --node-id "$node_id" --no-confirm \
      --host "http://${recover_addr}" --token "${INFLUXDB3_AUTH_TOKEN:-}" || true
  fi
  kill -TERM "$recover_pid" 2>/dev/null || true
  wait "$recover_pid" 2>/dev/null || true

  # Stage 3: surface partially written WAL files the recovery server rejected.
  # Stage 1 already removed the empty ones, so anything still reported corrupt is
  # non-empty and may hold partial data; print rm commands rather than deleting.
  corrupt=$(grep -F 'Skipping corrupt WAL file' "$recover_log" 2>/dev/null | grep -oE 'path=[^[:space:]]+\.wal' | cut -d= -f2- | tr -d '"' | sort -u || true)
  if [[ -z "$healthy" || -n "$corrupt" ]]; then
    log "stage 3: recovery server did not come up clean (see $recover_log)"
    if [[ -n "$corrupt" ]]; then
      log "stage 3: partially written WAL files remain; run these to remove them:"
      while IFS= read -r path; do
        [[ "$path" == /* ]] || path="$data_dir/$path"
        if [[ -f "$path" ]]; then
          echo "    rm -f '$path'"
        fi
      done <<<"$corrupt"
    fi
  fi
fi

exec /usr/bin/entrypoint.sh "$@"
