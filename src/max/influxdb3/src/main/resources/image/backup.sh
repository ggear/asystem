#!/bin/bash

set -euo pipefail

ENABLED="${INFLUXDB3_BACKUP_ENABLED:-true}"
MIN_INTERVAL="${INFLUXDB3_BACKUP_MIN_INTERVAL:-3600}"
CHAIN_MAX="${INFLUXDB3_BACKUP_CHAIN_MAX:-12}"
KEEP_CHAINS="${INFLUXDB3_BACKUP_KEEP_CHAINS:-2}"
TIMEOUT="${INFLUXDB3_BACKUP_TIMEOUT:-0}"
PROGRESS_INTERVAL="${INFLUXDB3_BACKUP_PROGRESS_INTERVAL:-30}"
DATA_DIR="${INFLUXDB3_DATA_DIR:-/asystem/mnt}"
CLUSTER_ID="${INFLUXDB3_CLUSTER_ID:-cluster_1}"
VERSION="${SERVICE_VERSION_ABSOLUTE:-unknown}"

DIR_BACKUP="${DATA_DIR}/${CLUSTER_ID}/backups"
LINK_BACKUP="${DATA_DIR}/backup"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

backups_listed() {
  [ -d "${DIR_BACKUP}" ] || return 0
  find "${DIR_BACKUP}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^(base|inc)-.*-[0-9]{8}T[0-9]{6}Z$' |
    sed -E 's/^(.*)-([0-9]{8}T[0-9]{6}Z)$/\2\t\1-\2/' |
    sort | cut -f2
}

backup_epoch() {
  local stamp="${1##*-}"
  date -u -d "${stamp:0:4}-${stamp:4:2}-${stamp:6:2}T${stamp:9:2}:${stamp:11:2}:${stamp:13:2}Z" +%s 2>/dev/null || echo 0
}

backup_reported() {
  influxdb3 status backup --name "$1" --format json 2>/dev/null
}

status_of() {
  printf '%s' "$1" | jq -r '.. | strings | select(test("^(completed|in_progress|failed)$"))' 2>/dev/null | head -1
}

progress_of() {
  printf '%s' "$1" | jq -c 'if type == "array" then .[0] else . end | del(..|nulls)' 2>/dev/null | head -1
}

backup_status() {
  status_of "$(backup_reported "$1")"
}

backup_awaited() {
  local name="$1" waited=0 payload status
  while true; do
    payload="$(backup_reported "${name}")"
    status="$(status_of "${payload}")"
    case "${status}" in
    completed) return 0 ;;
    failed)
      echo "Backup failed [${name}] progress [$(progress_of "${payload}")]" >&2
      return 1
      ;;
    esac
    if [ "${TIMEOUT}" -gt 0 ] && [ "${waited}" -ge "${TIMEOUT}" ]; then
      echo "Backup timed out [${name}] after [${waited}] seconds progress [$(progress_of "${payload}")]" >&2
      influxdb3 cancel backup --name "${name}" >/dev/null 2>&1 || true
      return 1
    fi
    sleep 5
    waited=$((waited + 5))
    if [ $((waited % PROGRESS_INTERVAL)) -lt 5 ]; then
      echo "Waiting for backup [${name}] status [${status:-unknown}] elapsed [${waited}] seconds progress [$(progress_of "${payload}")]"
    fi
  done
}

chains_pruned() {
  local names bases excess index
  mapfile -t names < <(backups_listed)
  bases=()
  for index in "${names[@]}"; do
    case "${index}" in
    base-*) bases+=("${index}") ;;
    esac
  done
  excess=$((${#bases[@]} - KEEP_CHAINS))
  for ((index = 0; index < excess; index++)); do
    echo "Deleting backup chain [${bases[${index}]}]"
    influxdb3 delete backup --name "${bases[${index}]}" --no-confirm >/dev/null 2>&1 ||
      echo "Delete failed for backup chain [${bases[${index}]}]" >&2
  done
}

if [ "${ENABLED}" != "true" ]; then
  echo "Backup disabled by [INFLUXDB3_BACKUP_ENABLED]"
  exit 0
fi

mapfile -t BACKUPS < <(backups_listed)

if [ "${#BACKUPS[@]}" -gt 0 ]; then
  NEWEST="${BACKUPS[-1]}"
  AGE=$(($(date -u +%s) - $(backup_epoch "${NEWEST}")))
  if [ "${AGE}" -lt "${MIN_INTERVAL}" ]; then
    echo "Backup skipped, newest backup [${NEWEST}] is [${AGE}] seconds old, minimum interval [${MIN_INTERVAL}] seconds"
    exit 0
  fi
fi

CHAIN_START=-1
for INDEX in "${!BACKUPS[@]}"; do
  case "${BACKUPS[${INDEX}]}" in
  base-*) CHAIN_START="${INDEX}" ;;
  esac
done

PARENT=""
if [ "${CHAIN_START}" -ge 0 ]; then
  CHAIN_LENGTH=$((${#BACKUPS[@]} - CHAIN_START))
  TAIL="${BACKUPS[-1]}"
  if [ "${CHAIN_LENGTH}" -ge "${CHAIN_MAX}" ]; then
    echo "Rebasing, chain [${BACKUPS[${CHAIN_START}]}] holds [${CHAIN_LENGTH}] backups, maximum [${CHAIN_MAX}]"
  elif [ "$(backup_status "${TAIL}")" != "completed" ]; then
    echo "Rebasing, chain tail [${TAIL}] is not complete"
  else
    PARENT="${TAIL}"
  fi
fi

if [ -n "${PARENT}" ]; then
  NAME="inc-${VERSION}-${STAMP}"
else
  NAME="base-${VERSION}-${STAMP}"
fi

echo -n "Starting backup [${NAME}] to [${DIR_BACKUP}] "
if [ -n "${PARENT}" ]; then
  echo -n "incremental from parent [${PARENT}] "
  influxdb3 create backup --name "${NAME}" --incremental --parent "${PARENT}" >/dev/null
else
  influxdb3 create backup --name "${NAME}" >/dev/null
fi
echo "... waiting"

backup_awaited "${NAME}"
echo "Completed backup [${NAME}]"

chains_pruned

if [ -d "${DIR_BACKUP}" ] && [ ! -e "${LINK_BACKUP}" ]; then
  ln -sfn "${CLUSTER_ID}/backups" "${LINK_BACKUP}"
fi
