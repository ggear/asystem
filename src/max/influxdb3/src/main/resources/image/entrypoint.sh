#!/bin/bash
# Wrapper around the stock /usr/bin/entrypoint.sh that heals two kinds of damage
# left by an unclean shutdown (power loss, or SIGKILL after the docker stop grace
# period) before serving:
#   1. Empty/truncated trailing WAL files. Replay skips them ("WAL file too
#      small"), but the writer then collides with the same numbered file on disk
#      and aborts with "another process has written to the WAL ahead of this one".
#   2. A stale ingest node registration: node_<n> stays marked as the live
#      ingester, so `serve` aborts with "... still running in another process".
#      A query-mode server does not claim the ingest role, so it starts despite
#      the stale registration and can mark the node stopped via `stop node`.
set -euo pipefail

node_id="${INFLUXDB3_NODE_IDENTIFIER_PREFIX:-}"
data_dir="${INFLUXDB3_DB_DIR:-/asystem/mnt}"

if [[ ("${1:-}" == serve || "${1:-}" == influxdb3 || "${1:-}" =~ ^-) \
      && -n "$node_id" && -d "$data_dir/$node_id" ]]; then
  wal_dir="$data_dir/$node_id/wal"
  if [[ -d "$wal_dir" ]]; then
    echo "entrypoint: removing empty/truncated WAL files under '$wal_dir'"
    find "$wal_dir" -maxdepth 1 -type f -name '*.wal' -size -12c -print -delete || true
  fi

  echo "entrypoint: clearing any stale ingest registration for node '$node_id'"
  recover_addr="127.0.0.1:18181"
  influxdb3 serve --mode query --http-bind "$recover_addr" >/tmp/recover.log 2>&1 &
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
  else
    echo "entrypoint: recovery server did not become healthy, continuing (see /tmp/recover.log)"
  fi
  kill -TERM "$recover_pid" 2>/dev/null || true
  wait "$recover_pid" 2>/dev/null || true
fi

exec /usr/bin/entrypoint.sh "$@"
