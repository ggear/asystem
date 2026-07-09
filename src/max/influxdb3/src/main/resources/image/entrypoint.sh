#!/bin/bash
# Wrapper around the stock /usr/bin/entrypoint.sh that clears a stale ingest
# node registration before serving. An unclean shutdown (power loss, or SIGKILL
# after the docker stop grace period) leaves node_<n> marked as the live
# ingester, so the next `serve` aborts with "... still running in another
# process". A query-mode server does not claim the ingest role, so it starts
# despite the stale registration and can mark the node stopped via `stop node`.
set -euo pipefail

node_id="${INFLUXDB3_NODE_IDENTIFIER_PREFIX:-}"
data_dir="${INFLUXDB3_DB_DIR:-/asystem/mnt}"

if [[ ("${1:-}" == serve || "${1:-}" == influxdb3 || "${1:-}" =~ ^-) \
      && -n "$node_id" && -d "$data_dir/$node_id" ]]; then
  echo "entrypoint: clearing any stale ingest registration for node '$node_id'"
  influxdb3 serve --mode query >/tmp/recover.log 2>&1 &
  recover_pid=$!
  healthy=""
  for _ in $(seq 1 30); do
    if [[ "$(curl -fsS http://127.0.0.1:8181/health \
          -H "Authorization: Bearer ${INFLUXDB3_AUTH_TOKEN:-}" 2>/dev/null)" == "OK" ]]; then
      healthy=1
      break
    fi
    kill -0 "$recover_pid" 2>/dev/null || break
    sleep 1
  done
  if [[ -n "$healthy" ]]; then
    influxdb3 stop node --node-id "$node_id" --no-confirm \
      --host http://127.0.0.1:8181 --token "${INFLUXDB3_AUTH_TOKEN:-}" || true
  else
    echo "entrypoint: recovery server did not become healthy, continuing (see /tmp/recover.log)"
  fi
  kill -TERM "$recover_pid" 2>/dev/null || true
  wait "$recover_pid" 2>/dev/null || true
fi

exec /usr/bin/entrypoint.sh "$@"
