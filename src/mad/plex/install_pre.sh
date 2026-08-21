#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env"

FAILED=0

mapfile -t SHARE_DIRS < <(find /share -mindepth 1 -maxdepth 1 -type d | sort)

if [ "${#SHARE_DIRS[@]}" -eq 0 ]; then
  echo "Error: No shares found under [/share]"
  exit 1
fi

for SHARE_DIR in "${SHARE_DIRS[@]}"; do
  [ -d "${SHARE_DIR}/media" ] && continue
  if ! grep -qE '^[^#].*[[:space:]]+'"${SHARE_DIR}"'[[:space:]]' /etc/fstab; then
    echo "Error: No fstab entry for share [${SHARE_DIR}]"
    FAILED=1
    continue
  fi
  mountpoint -q "${SHARE_DIR}" && umount -f "${SHARE_DIR}"
  mount "${SHARE_DIR}"
  if [ ! -d "${SHARE_DIR}/media" ]; then
    echo "Error: Could not mount share [${SHARE_DIR}]"
    FAILED=1
  fi
done

exit "${FAILED}"
