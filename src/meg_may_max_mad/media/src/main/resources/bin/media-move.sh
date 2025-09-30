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
          find "${share_current_dir}" -mindepth 1 -type d -empty -delete 2>/dev/null
        fi
      done
    else
      echo "Error: Share directory [${share_dest}] does not exist"
    fi
  else
    if [ $(mount | grep "${share_dir}" | grep -v "//" | wc -l) -gt 0 ]; then
      if [[ $(echo "${share_suffix}" | grep -o "/" | wc -l) -ge 2 ]]; then
        echo ${share_dir}
        echo ${share_suffix}
        echo rsync -avhPr /share/3/media/kids /share/2/media
      else
        echo "Error: Current directory [${current_dir}] is a share, but not nested in a library"
      fi
    else
      echo "Error: Current directory [${current_dir}] is not directly attached"
    fi
  fi
else
  echo "Error: Current directory [${current_dir}] is not a share"
fi
