#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

FILE_NAME_TOKEN="$*"
if [ -z "${FILE_NAME_TOKEN}" ]; then
  echo "Usage: ${0} <file-name-token>"
  exit 1
fi

share_ssh=()
if [ "${SHARE_ROOT}" != "/share" ]; then
  share_ssh=(ssh root@macmini-mad)
  echo "Executing remotely ..."
fi
declare -A dirs_found
while IFS= read -r file_found; do
  if [[ "${file_found}" == *"/series/"* ]]; then
    dir_found="${file_found%/Season */*}"
  else
    dir_found="${file_found%/*}"
  fi
  dirs_found["${dir_found}"]="${dir_found}"
done < <(
  "${share_ssh[@]}" bash -s <<EOF
find /share -type f ! -name "._*" ! -path "*/audio/*" -path "*/media/*" -iname "*${FILE_NAME_TOKEN}*"
EOF
)
printf '%s\n' "${dirs_found[@]}" | sort | while read -r dir_found; do
  dir_found="${dir_found/#\/share/$SHARE_ROOT}"
  if [ -n "${dir_found}" ]; then
    echo "cd '${dir_found}'"
  fi
done
