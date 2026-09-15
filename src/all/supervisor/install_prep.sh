#!/bin/bash

set -Eeuo pipefail

BACKUP_MOUNT="${BACKUP_MOUNT:-/backup}"
BACKUP_FSTAB="${BACKUP_FSTAB:-/etc/fstab}"

grep -qE "^[^#][^[:space:]]*[[:space:]]+${BACKUP_MOUNT}[[:space:]]" "${BACKUP_FSTAB}" 2>/dev/null || exit 0

if [[ ! -d "${BACKUP_MOUNT}" ]]; then
  mkdir -p "${BACKUP_MOUNT}"
  chmod 750 "${BACKUP_MOUNT}"
fi

if mountpoint -q "${BACKUP_MOUNT}"; then
  echo "Left [${BACKUP_MOUNT}] alone, it is mounted and the flag belongs on the bare mountpoint" >&2
  exit 0
fi

if [[ -n "$(find "${BACKUP_MOUNT}" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "Left [${BACKUP_MOUNT}] alone, it holds $(du -sh "${BACKUP_MOUNT}" | cut -f1) written while unmounted, delete that first" >&2
  exit 0
fi

if ! chattr +i "${BACKUP_MOUNT}" 2>/dev/null; then
  echo "Could not make [${BACKUP_MOUNT}] immutable, a failed mount can still fill the root filesystem" >&2
  exit 0
fi

echo "Protected [${BACKUP_MOUNT}] against a write while unmounted"
