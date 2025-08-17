#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SHARE_DIRS_SPACE=${SHARE_DIRS_LOCAL}
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  SHARE_DIRS_SPACE="${SHARE_DIR_MEDIA}"
elif [ -n "${SHARE_DIR}" ]; then
  SHARE_DIRS_SPACE="${SHARE_DIR}"
fi
echo "Space summary ... "

# INFO: Hack before I add totals to duf fork and potentially push upstream
SHARE_USAGE_CMD="duf -width 250 -style ascii -output mountpoint,size,used,avail,usage ${SHARE_DIRS_SPACE}"
if [ $(uname) == "Darwin" ]; then
  ${SHARE_USAGE_CMD} && ${SHARE_USAGE_CMD} | awk '
/\| \/Users/ {
    gsub(/\|/, "", $0)
    gsub(/^ +| +$/, "", $0)
    size=$2; used=$3; avail=$4
    sub(/T/,"",size); sub(/T/,"",used); sub(/T/,"",avail)
    total_size += size
    total_used += used
    total_avail += avail
}
END {
    printf "| TOTAL                          | %5.2fT | %5.2fT | %5.2fT |\n", total_size, total_used, sprintf("%.3f", total_avail)
    printf "+--------------------------------+--------+--------+--------+\n"
}'
else
  ${SHARE_USAGE_CMD}
fi
