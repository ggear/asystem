#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

shares_file="${LIB_ROOT}/../../shares.csv"
if [[ -f "${shares_file}" ]] && ! grep -q "^${HOSTNAME}," "${shares_file}"; then
  while IFS=',' read -r share_host share_index; do
    if [[ -z "${share_host}" || -z "${share_index}" ]]; then
      continue
    fi
    share_dir="${HOME}/Desktop/share/${share_index}"
    share_samba="//GUEST:@${share_host}/share-${share_index}"
    mkdir -p "${share_dir}"
    if [[ ! -d "${share_dir}/tmp" ]]; then
      echo -n "Mounting '${share_samba}' ... "
      diskutil unmount force "${share_dir}" &>/dev/null
      mount_smbfs -o soft,nodatacache,nodatacache "${share_samba}" "${share_dir}" && echo "done"
    fi
  done <"${shares_file}"
fi
