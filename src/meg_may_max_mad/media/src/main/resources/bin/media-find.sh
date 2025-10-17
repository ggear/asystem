#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

FILE_NAME_TOKEN="$*"
if [ -z "${FILE_NAME_TOKEN}" ]; then
  echo "Usage: ${0} <file-name-token>"
  exit 1
fi

share_ssh=""
[ "${SHARE_ROOT}" != "/share" ] && share_ssh="ssh root@macmini-mad" && echo "Executing remotely ..."
if [ "$(${share_ssh} '[[ $(find /share -mindepth 1 -maxdepth 1 | wc -l) -eq $(find /share -mindepth 2 -maxdepth 2 -name media -type d | wc -l) ]] && echo true || echo false')" == "true" ]; then
  declare -A dirs_found
  while read -r file_found; do
    if [[ "${file_found}" == *"/series/"* ]]; then
      dir_found="${file_found%/Season */*}"
    else
      dir_found="${file_found%/*}"
    fi
    dirs_found["${dir_found}"]="${dir_found}"
  done < <(${share_ssh} "find /share ! -name '._*' ! -path '*/audio/*' -path '*/media/*' -type f -iname '*${FILE_NAME_TOKEN}*'" | sed "s|^/share|${SHARE_ROOT}|")
  printf '%s\n' "${dirs_found[@]}" | sort | while read -r dir_found; do
    if [ ! -z "${dir_found}" ]; then
      echo "cd '${dir_found}'"
    fi
  done
else
  echo "Error: Not all shares are properly mounted."
fi
