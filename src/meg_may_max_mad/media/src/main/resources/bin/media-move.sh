#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

# Notes: Command line parameter acts as destination share index for "rsync workflow",
# or destination share scope for "mv workflow", defaulting to below if not passed
SHARE_INDEX_DESTINATION_DEFAULT="11"
SHARE_SCOPE_DESTINATION_DEFAULT="parents"

current_dir="${PWD}"
if [[ "${current_dir}" == *"/share/"* ]]; then
  share_prefix="${current_dir%%/share/*}"
  share_suffix="${current_dir#${share_prefix}/share/}"
  share_index="${share_suffix%%/*}"
  share_dir="${share_prefix}/share/${share_index}"
  share_suffix="${share_suffix#${share_index}/*}"
  if [[ "${share_suffix}" != "${share_index}" && ! "${share_suffix}" =~ ^media.* ]]; then

    # START: mv workflow
    share_dest="${share_dir}/media/${1:-${SHARE_SCOPE_DESTINATION_DEFAULT}}"
    if [ ! -d "${share_dest}" ]; then
      echo "Error: Share directory [${share_dest}] does not exist"
    else
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
    fi
    # END: mv workflow

  else

    # START: rsync workflow
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
        echo "Error: Current directory [${current_dir}] is not directly attached, nor can it be found on any SAMBA share"
      else
        share_src="/share/${share_index}/${share_suffix}/"
        share_index_dest="${1:-${SHARE_INDEX_DESTINATION_DEFAULT}}"
        if ! [[ "$share_index_dest" =~ ^[0-9]+$ ]]; then
          echo "Error: Share index [${share_index_dest}] is not an integer"
        else
          share_dest="/share/${share_index_dest}/media/$(echo ${share_suffix} | cut -d '/' -f2-)/"

#          ${share_ssh} bash -s -- "${share_src}" "${share_dest}" <<'EOF'
#if [ -n "${1}" ] && [ -d "${1}" ] && [ -n "${2}" ]; then
#  if [[ "${1}" == /share/* ]] && [[ $(echo "${1}" | grep -o "/" | wc -l) -ge 5 ]] && [[ $(mount | grep "$(echo "${1}" | cut -d'/' -f1-3)" | grep "//" | wc -l) -eq 0 ]] &&
#     [[ "${2}" == /share/* ]] && [[ $(echo "${2}" | grep -o "/" | wc -l) -ge 5 ]] && [[ $(mount | grep "$(echo "${2}" | cut -d'/' -f1-3)" | wc -l) -gt 0 ]]; then
#    share_rsync=(rsync -avhPr --info=progress2 "${1}" "${2}")
#    set -vx
#    mkdir -p "${2}"
#    if "${share_rsync[@]}"; then
#      rm -rvf "${1}"*
#      find "${1}.." -type d -empty -delete 2>/dev/null
#    else
#      echo "Error: Failed to rsync files from source [${1}] to destination [${2}]"
#    fi
#  else
#    echo "Error: Source [${1}] and or destination [${2}] paths are invalid"
#  fi
#else
#    echo "Error: Source [${1}] and or destination [${2}] paths are null"
#fi
#EOF

          ${share_ssh} bash -s -- "${share_src}" "${share_dest}" <<'EOF'
set -euo pipefail
src="${1}"
dest="${2}"
if [ -z "${src}" ] || [ ! -d "${src}" ] || [ -z "${dest}" ]; then
    echo "Error: Source [${src}] or destination [${dest}] invalid or missing"
    exit 1
fi
count_slashes() { echo "${1}" | awk -F'/' '{print NF-1}'; }
if [[ "${src}" != /share/* ]] || [[ $(count_slashes "${src}") -lt 5 ]] || \
   [[ "${dest}" != /share/* ]] || [[ $(count_slashes "${dest}") -lt 5 ]]; then
    echo "Error: Source [${src}] or destination [${dest}] paths do not meet criteria"
    exit 1
fi
src_mount=$(echo "${src}" | cut -d'/' -f1-3)
dest_mount=$(echo "${dest}" | cut -d'/' -f1-3)
if ! mount | grep -q "${src_mount}"; then
    echo "Error: Source mount [${src_mount}] not found"
    exit 1
fi
if ! mount | grep -q "${dest_mount}"; then
    echo "Error: Destination mount [${dest_mount}] not found"
    exit 1
fi
mkdir -p "${dest}"
rsync_opts=(-avhPr --info=progress2)
echo "===== DRY RUN ====="
rsync --dry-run "${rsync_opts[@]}" "${src}" "${dest}"
echo "==================="
read -p "Proceed with actual sync? [y/N]: " proceed
if [[ "${proceed}" != "y" && "${proceed}" != "Y" ]]; then
    echo "Aborted by user."
    exit 0
fi
if rsync "${rsync_opts[@]}" "${src}" "${dest}"; then
    find "${src}" -mindepth 1 -maxdepth 1 -exec rm -rvf {} +
    find "${src}/.." -type d -empty -delete 2>/dev/null
else
    echo "Error: Rsync failed from [${src}] to [${dest}]"
    exit 1
fi
EOF







        fi
      fi
    else
      echo "Error: Current directory [${current_dir}] is a share, but not nested in a library"
    fi
    # END: rsync workflow

  fi
else
  echo "Error: Current directory [${current_dir}] is not a share"
fi
