#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

DEST_SHARE_SCOPE="${1:-"parents"}"
DEST_SHARE_INDEX="${2:-"11"}"

current_dir="${PWD}"
if [[ "${current_dir}" == *"/share/"* ]]; then
  share_prefix="${current_dir%%/share/*}"
  share_suffix="${current_dir#${share_prefix}/share/}"
  share_index="${share_suffix%%/*}"
  share_dir="${share_prefix}/share/${share_index}"
  share_suffix="${share_suffix#${share_index}/*}"
  if [[ "${share_suffix}" != "${share_index}" && ! "${share_suffix}" =~ ^media.* ]]; then
    share_dest="${share_dir}/media/${DEST_SHARE_SCOPE}"
    if [ -d "${share_dest}" ]; then
      for share_type in series movies; do
        share_type_dir=""
        if [[ "${share_suffix}" == *"/${share_type}/"* ]]; then
          share_current_dir="${current_dir}"
          share_type_dir="${current_dir%%/${share_type}/*}/${share_type}"
        else
          share_suffix_find="$(find "${current_dir}" -name "${share_type}" -type d)"
          if [ ! -z "${share_suffix_find}" ]; then
            share_current_dir="${share_suffix_find}"
            share_type_dir="${share_suffix_find}"
          fi
        fi
        if [ ! -z "${share_type_dir}" ]; then
          share_type_suffix="${share_current_dir#${share_type_dir}}"
          share_type_dest="${share_dest}/${share_type}"
          find "${share_type_dir}" -mindepth 1 -type d -print0 | while IFS= read -r -d '' dir; do
            rel_dir="${dir#${share_type_dir}/}"
            target_dir="${share_type_dest}/${rel_dir}"
            if [[ -z "${share_type_suffix}" ]] || [[ "${target_dir}" == *"${share_type_suffix}"* ]]; then
              mkdir -p "${target_dir}"
            fi
          done
          find "${share_current_dir}" -mindepth 1 -type f -print0 | while IFS= read -r -d '' file; do
            source_file="${file}"
            target_file="${share_type_dest}/${file#${share_type_dir}/}"
            mv -v "${source_file}" "${target_file}"
          done
          find "${share_current_dir}" -mindepth 1 -type d -empty -delete
        fi
      done
    else
      echo "Error: Share directory [${share_dest}] does not exist"
    fi
  else
    if [[ $(echo "${share_suffix}" | grep -o "/" | wc -l) -ge 2 ]]; then
      share_ssh=""
      if [ $(mount | grep "${share_dir}" | grep "//" | wc -l) -gt 0 ]; then
        for share_label in $(basename "$(realpath $(asystem-media-home)/../../../../..)" | tr "_" "\\n"); do
          share_host="$(grep "${share_label}" "$(asystem-media-home)/../../../../../../../.hosts" | cut -d "=" -f 2 | cut -d "," -f 1)""-${share_label}"
          share_current_dir_host='. $(asystem-media-home)/.env_media; echo ${SHARE_DIRS_LOCAL} | grep ${SHARE_ROOT}/'"${share_index}"' | wc -l'
          if host "${share_host}" >/dev/null 2>&1; then
            if [ $(ssh "root@${share_host}" "${share_current_dir_host}") -gt 0 ]; then
              share_ssh="ssh root@${share_host}"
            fi
          fi
        done
      fi
      if [ $(mount | grep "${share_dir}" | grep "//" | wc -l) -gt 0 ] && [ -z "${share_ssh}" ]; then
        echo "Error: Current directory [${current_dir}] is not directly attached, nor can it be founf on any SAMBA share"
      else
        share_src="/share/${share_index}/${share_suffix}/"
        share_dest="/share/${DEST_SHARE_INDEX}/media/${DEST_SHARE_SCOPE}/$(echo ${share_suffix} | cut -d '/' -f3-)/"
        eval "${share_ssh}" bash -s "${share_src}" "${share_dest}" <<'EOF'
set -vx
mkdir -p "${2}"
share_rsync=(rsync -avhPr "${1}" "${2}")
if "${share_rsync[@]}"; then
    rm -rvf "${1}/"*
    find "${1}/.." -type d -empty -delete
else
    echo "Error: Failed to rsync files from [${1}] to [${2}]"
fi
EOF
      fi
    else
      echo "Error: Current directory [${current_dir}] is a share, but not nested in a library"
    fi
  fi
else
  echo "Error: Current directory [${current_dir}] is not a share"
fi
