#!/usr/bin/env bash

set -uo pipefail

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env_media"

MEDIA_ACTIONS=(rename check merge upscale transcode reformat downscale)

declare -A MEDIA_ACTION_HELP=(
  [rename]="apply the canonical naming"
  [check]="verify streams and subtitles"
  [merge]="merge a split title, never in process"
  [upscale]="raise resolution to target"
  [transcode]="re-encode to the target quality"
  [reformat]="remux without re-encoding"
  [downscale]="lower resolution to target"
)

MEDIA_BIN_INSTALL="/var/lib/asystem/install/media/latest/bin"

MEDIA_SHARES_FILE="${ROOT_DIR}/../shares.csv"

MEDIA_SCOPE_DEFAULT="parents"

PUBLISH_SCOPE="${MEDIA_SCOPE_DEFAULT}"

OPT_FORCE=0
OPT_PERSISTENT=0
OPT_SHARE=""
OPT_QUIET=0
OPT_VERBOSE=0
OPT_DRY_RUN=0

COMMAND=""
POSITIONAL=""

EXTENT=""
EXTENT_SHARE_DIR=""

SHARE_PATH_DIR=""
SHARE_PATH_INDEX=""
SHARE_PATH_SUFFIX=""

usage() {
  cat <<'EOF'
Usage: amedia [command] [argument] [options]

  Pipeline             stop at the first failed stage
    publish   [scope]  stow, process, merge, refresh             (default: parents)
    process            normalise, analyse, act, report space
    analyse            probe the library, write the scripts

  Actions              run what analyse wrote, writing it if absent
EOF
  local action
  for action in "${MEDIA_ACTIONS[@]}"; do
    printf '    %-19s%s\n' "${action}" "${MEDIA_ACTION_HELP[${action}]}"
  done
  cat <<'EOF'

  Library
    clean     [dir]    delete generated metadata and scripts     (default: from $PWD)
    normalise [dir]    fix ownership and modes, strip junk       (default: from $PWD)
    ingress   [dir]    import the usb drive and downloads        (default: from $PWD)
    stow      [scope]  file staged content into the library      (default: parents)
    move      <share>  copy to another share, drop the source
    refresh            reconcile paths into downstream stores
    truncate           trim the online shared history

  Inspect
    find      <token>  find a media artefact
    metadata           print this media artefact's spec and probes
    space              print share usage

  Tool
    mount              mount the remote shares, Darwin
    home               print the install bin directory
    help               this text, and a bare amedia prints it

  --share      <index> one share, not the one you are in         (default: all local)
  --force              analyse only, re-probe every file first   (default: off)
  --persistent         carry on past a failed pipeline stage     (default: off)
  --quiet              summaries only, the default below a share (default: off)
  --verbose            one line per file, the default in a share (default: off)
  --dryrun             move only, print it and change nothing    (default: off)
EOF
}

refuse() {
  echo "amedia ${1}" >&2
  usage >&2
  exit 2
}

in_media_file_root() {
  [ -n "${SHARE_DIR_MEDIA}" ] || return 1
  local parent parent2
  parent="$(basename "$(dirname "${PWD}")")"
  parent2="$(basename "$(dirname "$(dirname "${PWD}")")")"
  [[ "${parent}" == "movies" || "${parent}" == "series" || "${parent2}" == "series" ]]
}

resolve_extent() {
  SHARE_PATH_DIR=""
  SHARE_PATH_INDEX=""
  SHARE_PATH_SUFFIX=""
  if [ -n "${SHARE_DIR}" ] && [[ "${PWD}" == "${SHARE_DIR}" || "${PWD}" == "${SHARE_DIR}/"* ]]; then
    SHARE_PATH_DIR="${SHARE_DIR}"
    SHARE_PATH_INDEX="$(basename "${SHARE_DIR}")"
    if [ "${PWD}" = "${SHARE_DIR}" ]; then
      SHARE_PATH_SUFFIX="${SHARE_PATH_INDEX}"
    else
      SHARE_PATH_SUFFIX="${PWD#"${SHARE_DIR}"/}"
    fi
  fi
  if [ -n "${OPT_SHARE}" ]; then
    local match="" _dir
    for _dir in ${SHARE_DIRS_LOCAL}; do
      [[ "$(basename "${_dir}")" == "${OPT_SHARE}" ]] && match="${_dir}"
    done
    [ -n "${match}" ] || refuse "share [${OPT_SHARE}] is not held by this host"
    EXTENT="share"
    EXTENT_SHARE_DIR="${match}"
    return
  fi
  if [ -n "${SHARE_DIR_MEDIA}" ]; then
    if in_media_file_root; then EXTENT="file"; else EXTENT="media"; fi
    EXTENT_SHARE_DIR="${SHARE_DIR}"
  elif [ -n "${SHARE_DIR}" ]; then
    EXTENT="share"
    EXTENT_SHARE_DIR="${SHARE_DIR}"
  else
    EXTENT="local"
  fi
}

in_list() {
  local needle="${1}" item
  shift
  for item in "$@"; do
    [ "${item}" = "${needle}" ] && return 0
  done
  return 1
}

path_slashes() {
  local slashes="${1//[!\/]/}"
  echo "${#slashes}"
}

resolve_verbosity() {
  if [ "${OPT_VERBOSE}" -eq 1 ]; then
    echo "verbose"
  elif [ "${OPT_QUIET}" -eq 1 ]; then
    echo "quiet"
  else
    echo ""
  fi
}

analyse_share() {
  local dir="${1}" subpath="${2}" verbosity="${3}"
  local script="${dir}/tmp/scripts/media/analyse.sh"
  if [ -f "${script}" ]; then
    "${script}" "--${verbosity}" "${subpath}"
  else
    local target="${dir}"
    [ "${subpath}" = "media" ] && target="${dir}/media"
    "${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" "--${verbosity}" "${target}" "${MEDIA_GOOGLE_SHEET_GUID}"
  fi
}

analyse_extent() {
  local dir="${1}" verbosity subpath
  verbosity="$(resolve_verbosity)"
  if [ "${EXTENT}" = "local" ]; then
    subpath="/"
    verbosity="${verbosity:-quiet}"
  else
    subpath="media"
    verbosity="${verbosity:-verbose}"
  fi
  analyse_share "${dir}" "${subpath}" "${verbosity}"
}

command_analyse() {
  local result=0
  local verbosity
  verbosity="$(resolve_verbosity)"
  case "${EXTENT}" in
  file | media)
    library_clean "${PWD}" || result=1
    "${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" "--${verbosity:-verbose}" "${PWD}" "${MEDIA_GOOGLE_SHEET_GUID}" || result=1
    ;;
  share)
    if [ "${OPT_FORCE}" -eq 1 ]; then
      echo "amedia force re-probing extent [share] [${EXTENT_SHARE_DIR}]"
      library_clean "${EXTENT_SHARE_DIR}" || result=1
    fi
    analyse_extent "${EXTENT_SHARE_DIR}" || result=1
    ;;
  local)
    [ "${OPT_FORCE}" -eq 1 ] && echo "amedia force re-probing extent [local]"
    local _dir
    for _dir in ${SHARE_DIRS_LOCAL}; do
      if [ "${OPT_FORCE}" -eq 1 ]; then
        library_clean "${_dir}" || result=1
      fi
      analyse_extent "${_dir}" || result=1
    done
    ;;
  esac
  return ${result}
}

dispatch_action() {
  local verb="${1}"
  local result=0
  case "${EXTENT}" in
  file | media)
    local action
    while IFS= read -r -d '' action; do
      "${action}" || result=1
    done < <(${FIND_CMD} . -name "${verb}.sh" -print0)
    ;;
  share | local)
    local dirs
    if [ "${EXTENT}" = "share" ]; then dirs="${EXTENT_SHARE_DIR}"; else dirs="${SHARE_DIRS_LOCAL}"; fi
    local _dir
    for _dir in ${dirs}; do
      local script="${_dir}/tmp/scripts/media/${verb}.sh"
      if [ ! -f "${script}" ]; then
        analyse_extent "${_dir}" || result=1
      fi
      [ -f "${script}" ] && { "${script}" || result=1; }
    done
    ;;
  esac
  return ${result}
}

library_clean() {
  local working_dir="${1}"
  [ -d "${working_dir}" ] || {
    echo "amedia [${working_dir}] is not a directory" >&2
    return 1
  }
  local result=0 action log
  log="$(mktemp -t amedia-clean.XXXXXX)"
  echo -n "Cleaning [${working_dir}] ... "
  {
    ${FIND_CMD} "${working_dir}" -name ".DS_Store" -type f -delete || result=1
    ${FIND_CMD} "${working_dir}" -name "._metadata_*.yaml" -type f -delete || result=1
    ${FIND_CMD} "${working_dir}" -name "._defaults_analysed_*.yaml" -type f -delete || result=1
    for action in "${MEDIA_ACTIONS[@]}"; do
      ${FIND_CMD} "${working_dir}" -name "${action}.sh" -type f -delete || result=1
      ${FIND_CMD} "${working_dir}" -name "._${action}_*" -type d -prune -exec rm -rf '{}' + || result=1
    done
    [ -d "${working_dir}" ] && { ${FIND_CMD} "${working_dir}" -path "*/share/*/media/*" -type d -empty -delete || result=1; }
  } >"${log}" 2>&1
  if [ "${result}" -ne 0 ]; then
    echo "failed"
    cat "${log}"
    rm -f "${log}"
    return 1
  fi
  rm -f "${log}"
  echo "done"
  return 0
}

# shellcheck disable=SC2329
normalise_permissions() {
  local normalise_dir="${1}" dir_mode="${2}" script_mode="${3}" file_mode="${4}"
  local result=0
  [ -d "${normalise_dir}" ] || return 0
  if command -v setfacl &>/dev/null; then
    setfacl -bR "${normalise_dir}" || result=1
  fi
  if id "graham" &>/dev/null && getent group "users" &>/dev/null; then
    chown -R "graham:users" "${normalise_dir}" || result=1
  fi
  ${FIND_CMD} "${normalise_dir}" -type d -exec chmod "${dir_mode}" {} + || result=1
  ${FIND_CMD} "${normalise_dir}" -type f -name "*.sh" -exec chmod "${script_mode}" {} + || result=1
  ${FIND_CMD} "${normalise_dir}" -type f ! -name "*.sh" -exec chmod "${file_mode}" {} + || result=1
  return "${result}"
}

# shellcheck disable=SC2329
normalise_share_tmp_dir() {
  local working_dir="${1}" _dir
  # shellcheck disable=SC2153
  for _dir in ${SHARE_DIRS}; do
    if [[ "${working_dir}" == "${_dir}" || "${working_dir}" == "${_dir}/"* ]]; then
      echo "${_dir}/tmp/scripts"
      return
    fi
  done
}

# shellcheck disable=SC2329
library_normalise() {
  local working_dir="${1}"
  [ -d "${working_dir}" ] || {
    echo "amedia [${working_dir}] is not a directory" >&2
    return 1
  }
  local result=0
  echo -n "Normalising [${working_dir}] ... "
  if [ "$(uname)" == "Linux" ]; then
    normalise_permissions "${working_dir}" 2750 750 640 || result=1
    local share_tmp_dir
    share_tmp_dir="$(normalise_share_tmp_dir "${working_dir}")"
    if [ -n "${share_tmp_dir}" ]; then
      mkdir -p "${share_tmp_dir}" || result=1
      normalise_permissions "${share_tmp_dir}" 2770 770 660 || result=1
    fi
  fi
  ${FIND_CMD} "${working_dir}" -type f \( -name nohup -o -name .DS_Store -o \
    -regextype posix-extended -regex '.*/\.[^/]*\.[A-Za-z0-9]{6}$' \) -delete || result=1
  if [ "${result}" -ne 0 ]; then
    echo "failed"
    return 1
  fi
  echo "done"
  return 0
}

library_ingress_import() {
  local share_dir="${1}"
  local result=0
  if [ "$(lsblk -ro name,label | grep -c GRAHAM)" -eq 1 ]; then
    local import_dev
    import_dev="/dev/$(lsblk -ro name,label | grep GRAHAM | awk '{print $1}')"
    if [ -e "${import_dev}" ]; then
      echo "#######################################################################################"
      echo "Starting rsync of /media/usbdrive to ${share_dir}/tmp"
      echo "#######################################################################################"
      mkdir -p /media/usbdrive
      umount -fq /media/usbdrive
      mount -t exfat "${import_dev}" /media/usbdrive || result=1
      rsync -avP /media/usbdrive "${share_dir}/tmp" || result=1
      echo "" && echo "Completed rsync of /media/usbdrive to ${share_dir}/tmp" && date && echo ""
      echo "#######################################################################################"
    fi
  fi
  umount -fq /media/usbdrive >/dev/null 2>&1
  return ${result}
}

library_ingress_sweep() {
  local share_dir="${1}"
  local result=0
  echo -n "Sweeping [${share_dir}/tmp] ... "
  rm -rf \
    "${share_dir}/tmp/usbdrive/System Volume Information" \
    "${share_dir}/tmp/usbdrive/\$RECYCLE.BIN" \
    "${share_dir}"/tmp/usbdrive/..?* \
    "${share_dir}"/tmp/usbdrive/.[!.]* || result=1
  "${PYTHON_DIR}/python" "${LIB_ROOT}/ingress.py" "${share_dir}/tmp" || result=1
  if [ ${result} -ne 0 ]; then
    echo "failed"
    return 1
  fi
  echo "done"
  return 0
}

command_ingress() {
  local dir="${1:-}"
  if [ "$(uname)" != "Linux" ]; then
    echo "amedia ingress is Linux-only, skipping" >&2
    return 0
  fi
  local shares=()
  if [ -n "${dir}" ]; then
    local match="" _dir
    for _dir in ${SHARE_DIRS}; do
      [ "${_dir}" = "${dir}" ] && match="${_dir}"
    done
    [ -n "${match}" ] || refuse "[${dir}] is not a share root"
    shares=("${match}")
  else
    case "${EXTENT}" in
    file | media | share) shares=("${EXTENT_SHARE_DIR}") ;;
    local) read -r -a shares <<<"${SHARE_DIRS_LOCAL}" ;;
    esac
  fi
  if [ ${#shares[@]} -eq 0 ]; then
    echo "amedia no local share to ingress into" >&2
    return 0
  fi
  local result=0 import_ok=1
  library_ingress_import "${shares[0]}" || {
    import_ok=0
    result=1
  }
  local _share
  for _share in "${shares[@]}"; do
    if [ "${_share}" = "${shares[0]}" ] && [ ${import_ok} -eq 0 ]; then
      echo "amedia skipping sweep of [${_share}], the import failed" >&2
      continue
    fi
    library_ingress_sweep "${_share}" || result=1
  done
  return ${result}
}

dispatch_library() {
  local verb="${1}" dir="${2:-}"
  local result=0
  if [ -n "${dir}" ]; then
    "library_${verb}" "${dir}" || result=1
    return ${result}
  fi
  case "${EXTENT}" in
  file | media)
    "library_${verb}" "${PWD}" || result=1
    ;;
  share)
    local script="${EXTENT_SHARE_DIR}/tmp/scripts/media/${verb}.sh"
    if [ -f "${script}" ]; then "${script}" || result=1; else "library_${verb}" "${EXTENT_SHARE_DIR}" || result=1; fi
    ;;
  local)
    local _dir
    for _dir in ${SHARE_DIRS_LOCAL}; do
      local script="${_dir}/tmp/scripts/media/${verb}.sh"
      if [ -f "${script}" ]; then "${script}" || result=1; else "library_${verb}" "${_dir}" || result=1; fi
    done
    ;;
  esac
  return ${result}
}

share_path_is_outside_media() {
  [[ "${SHARE_PATH_SUFFIX}" != "${SHARE_PATH_INDEX}" && ! "${SHARE_PATH_SUFFIX}" =~ ^media.* ]]
}

command_stow() {
  local scope="${1:-${MEDIA_SCOPE_DEFAULT}}"
  [ -n "${SHARE_PATH_DIR}" ] || refuse "current directory [${PWD}] is not a share"
  if [ "${SHARE_PATH_SUFFIX}" = "${SHARE_PATH_INDEX}" ]; then
    refuse "current directory [${PWD}] is a bare share root, nothing there to stow"
  fi
  share_path_is_outside_media || refuse "already in the library, did you mean [amedia move <share>]"
  local share_dest="${SHARE_PATH_DIR}/media/${scope}"
  if [ ! -d "${share_dest}" ]; then
    echo "amedia share directory [${share_dest}] does not exist" >&2
    return 1
  fi
  local result=0 share_type
  for share_type in series movies audio; do
    local share_type_dir="" share_current_dir=""
    if [[ "${SHARE_PATH_SUFFIX}" == *"/${share_type}/"* ]]; then
      share_current_dir="${PWD}"
      share_type_dir="${PWD%%/"${share_type}"/*}/${share_type}"
    else
      local share_suffix_find
      share_suffix_find="$(${FIND_CMD} "${PWD}" -name "${share_type}" -type d)"
      if [ -n "${share_suffix_find}" ]; then
        share_current_dir="${share_suffix_find}"
        share_type_dir="${share_suffix_find}"
      fi
    fi
    if [ -n "${share_type_dir}" ]; then
      local share_type_suffix="${share_current_dir#"${share_type_dir}"}"
      local share_type_dest="${share_dest}/${share_type}"
      local dir file
      while IFS= read -r -d '' dir; do
        local rel_dir="${dir#"${share_type_dir}"/}"
        local target_dir="${share_type_dest}/${rel_dir}"
        if [[ -z "${share_type_suffix}" ]] || [[ "${target_dir}" == *"${share_type_suffix}"* ]]; then
          mkdir -p "${target_dir}" || result=1
        fi
      done < <(${FIND_CMD} "${share_type_dir}" -mindepth 1 -type d -print0)
      while IFS= read -r -d '' file; do
        local source_file="${file}"
        local target_file="${share_type_dest}/${file#"${share_type_dir}"/}"
        if [ -e "${target_file}" ]; then
          local target_dir="${target_file%/*}"
          local target_base="${target_file##*/}"
          local target_name="${target_base%.*}"
          local target_extension=""
          [ "${target_name}" != "${target_base}" ] && target_extension=".${target_base##*.}"
          local target_index=1
          while [ -e "${target_dir}/${target_name}_${target_index}${target_extension}" ]; do
            target_index=$((target_index + 1))
          done
          target_file="${target_dir}/${target_name}_${target_index}${target_extension}"
          echo "Warning: Target file already exists, moving [${source_file}] to [${target_file}] instead"
        fi
        mv -vn "${source_file}" "${target_file}" || result=1
      done < <(${FIND_CMD} "${share_current_dir}" -mindepth 1 -type f -print0)
      [ -d "${share_current_dir}/.." ] && ${FIND_CMD} "${share_current_dir}/.." -type d -empty -delete >/dev/null 2>&1
    fi
  done
  return ${result}
}

command_move() {
  local dest="${1:-}"
  [ -n "${dest}" ] || refuse "move requires a <share> argument"
  [[ "${dest}" =~ ^[0-9]+$ ]] || refuse "[${dest}] is not a share index, did you mean [amedia stow ${dest}]"
  [ -n "${SHARE_PATH_DIR}" ] || refuse "current directory [${PWD}] is not a share"
  share_path_is_outside_media && refuse "current directory is not nested in the library, did you mean [amedia stow <scope>]"
  local share_dashes
  share_dashes="$(path_slashes "${SHARE_PATH_SUFFIX}")"
  if [ "${share_dashes}" -lt 2 ]; then
    echo "amedia current directory [${PWD}] is a share, but not nested in a library" >&2
    return 1
  fi
  local result=0 share_mount
  local share_ssh=()
  share_mount="$(mount | grep " on ${SHARE_PATH_DIR} ")"
  if [ -n "${share_mount}" ] && [[ "${share_mount}" == *"//"* ]]; then
    while IFS=',' read -r share_host share_csv_index; do
      if [[ -z "${share_host}" || -z "${share_csv_index}" || "${share_csv_index}" != "${SHARE_PATH_INDEX}" ]]; then
        continue
      fi
      local share_current_dir_host=". ${MEDIA_BIN_INSTALL}/.env_media; echo \${SHARE_DIRS_LOCAL} | grep \${SHARE_ROOT}/${SHARE_PATH_INDEX} | wc -l"
      if host "${share_host}" >/dev/null 2>&1; then
        # shellcheck disable=SC2029
        if [ "$(ssh "root@${share_host}" "${share_current_dir_host}")" -gt 0 ]; then
          share_ssh=(ssh "root@${share_host}")
        fi
      fi
    done <"${MEDIA_SHARES_FILE}"
    if [ ${#share_ssh[@]} -eq 0 ]; then
      echo "amedia current directory [${PWD}] is not directly attached, nor can it be found on any SAMBA share" >&2
      return 1
    fi
  fi
  local share_src="/share/${SHARE_PATH_INDEX}/${SHARE_PATH_SUFFIX}/"
  local share_dest_suffix
  share_dest_suffix="$(echo "${SHARE_PATH_SUFFIX}" | cut -d '/' -f2-)"
  local share_dest="/share/${dest}/media/${share_dest_suffix}/"
  if [ "${OPT_DRY_RUN}" -eq 1 ]; then
    echo "+ rsync '${share_src}' -> '${share_dest}'"
    echo "+ rm -rvf '${share_src}'*"
    return 0
  fi
  local share_args=("${share_src}" "${share_dest}")
  if [ ${#share_ssh[@]} -gt 0 ]; then
    echo "Executing remotely ..."
    share_args=("$(printf '%q' "${share_src}")" "$(printf '%q' "${share_dest}")")
  fi
  # shellcheck disable=SC2064
  trap "${share_ssh[*]} pkill -9 -f 'rsync .*/share/${dest}/'; echo; exit" INT
  "${share_ssh[@]}" bash -s -- "${share_args[@]}" <<'EOF' || result=1
share_src="${1}"
share_dest="${2}"
result=0
if [ -n "${share_src}" ] && [ -d "${share_src}" ] && [ -n "${share_dest}" ]; then
  if [ "${share_src}" == "${share_dest}" ]; then
    echo "Error: Source [${share_src}] and destination [${share_dest}] paths are the same"
    result=1
  elif [[ "${share_src}" == /share/* ]] && [[ $(echo "${share_src}" | grep -o "/" | wc -l) -ge 5 ]] && [[ $(mount | grep "$(echo "${share_src}" | cut -d'/' -f1-3)" | grep "//" | wc -l) -eq 0 ]] &&
     [[ "${share_dest}" == /share/* ]] && [[ $(echo "${share_dest}" | grep -o "/" | wc -l) -ge 5 ]] && [[ $(mount | grep "$(echo "${share_dest}" | cut -d'/' -f1-3)" | wc -l) -gt 0 ]]; then
    mkdir -p "${share_dest}"
    source_size=$(( $(du -s "${share_src}" | cut -f1) / 1048576 ))
    dest_free=$(( $(df "${share_dest}" | tail -1 | awk '{print $4}') / 1048576 ))
    if [ "${dest_free}" -eq 0 ] || [ $(( source_size * 100 / dest_free )) -gt 95 ]; then
      echo "Error: Source size [${source_size} GB] is greater than 95% of free space [${dest_free} GB] on destination, bailing out"
      [ -d "$share_dest" ] && [ -z "$(ls -A "$share_dest")" ] && rm -rf "$share_dest"
      result=1
    else
      echo "+ rsync '$(echo "${share_src}" | sed -E 's|^(/share/[0-9]+).*|\1|')'(${source_size} GB files) -> '$(echo "${share_dest}" | sed -E 's|^(/share/[0-9]+).*|\1|')'(${dest_free} GB free)"
      set -vx
      if rsync -avhPr --info=progress2 "${share_src}" "${share_dest}"; then
        rm -rvf "${share_src}"*
        [[ $(echo "${share_src}" | grep -o "/" | wc -l) -gt 6 ]] && rm -rvf "${share_src}".[!.]*
        [ -d "${share_src}.." ] && find "${share_src}.." -type d -empty -delete >/dev/null 2>&1
      else
        echo "Error: Failed to rsync files from source [${share_src}] to destination [${share_dest}]"
        result=1
      fi
    fi
  else
    echo "Error: Source [${share_src}] and or destination [${share_dest}] paths are invalid"
    result=1
  fi
else
  echo "Error: Source [${share_src}] and or destination [${share_dest}] paths are null"
  result=1
fi
exit ${result}
EOF
  return ${result}
}

command_refresh() {
  export SABNZBD_URL SABNZBD_API_KEY
  export SONARR_URL SONARR_API_KEY
  export PLEX_URL PLEX_TOKEN
  "${PYTHON_DIR}/python" "${LIB_ROOT}/refresh.py" "${SHARE_ROOT}"
}

command_truncate() {
  "${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" "${SHARE_ROOT}" "${MEDIA_GOOGLE_SHEET_GUID}" --clean
}

command_find() {
  local token="${1:-}"
  [ -n "${token}" ] || refuse "find requires a <token> argument"
  local share_ssh=()
  if [ "${SHARE_ROOT}" != "/share" ]; then
    share_ssh=(ssh root@macmini-mad)
    echo "Executing remotely ..."
  fi
  "${share_ssh[@]}" bash -s <<EOF | while IFS= read -r file_found; do
find /share -type f ! -name "._*" ! -path "*/audio/*" -path "*/media/*" -iname "*${token}*"
EOF
    [ -n "${file_found}" ] || continue
    if [[ "${file_found}" == *"/series/"* ]]; then
      echo "${file_found%/Season */*}"
    else
      echo "${file_found%/*}"
    fi
  done | sort -u | while IFS= read -r dir_found; do
    dir_found="${dir_found/#\/share/${SHARE_ROOT}}"
    [ -n "${dir_found}" ] && echo "cd '${dir_found}'"
  done
  return 0
}

command_metadata() {
  if [ "${EXTENT}" != "file" ]; then
    echo "amedia metadata needs a movies or series file directory, not [${PWD}]" >&2
    return 1
  fi
  local defaults_file="._defaults.yaml"
  if [ ! -f "${defaults_file}" ]; then
    cat >"${defaults_file}" <<'EOF'
#- transcode_action: Ignore
#- target_quality: 6
#- target_channels: 2
#- target_lang: eng
#- native_lang: eng
EOF
  fi
  if [ "$(${FIND_CMD} . -name "._metadata_*.yaml" -type f | wc -l)" -le 11 ]; then
    ${FIND_CMD} . -name "._metadata_*.yaml" -type f -exec echo "" \; -exec echo "Metadata file:" \; -exec cat {} \;
  fi
  echo "" && echo "Defaults file:" && cat "${defaults_file}"
  echo "" && echo "Defaults edit:" && echo "vi ${defaults_file}"
  echo ""
  return 0
}

command_space() {
  command_mount
  local dirs result=0
  case "${EXTENT}" in
  file | media) dirs="${EXTENT_MEDIA_DIR}" ;;
  share) dirs="${EXTENT_SHARE_DIR}" ;;
  local) dirs="${SHARE_DIRS_LOCAL}" ;;
  esac
  echo "Space summary ... "
  # shellcheck disable=SC2086
  duf -width 250 -style ascii -output mountpoint,size,used,avail,usage ${dirs} || result=1
  return ${result}
}

mount_darwin() {
  local result=0
  if [[ -f "${MEDIA_SHARES_FILE}" ]] && ! grep -q "^${HOSTNAME}," "${MEDIA_SHARES_FILE}"; then
    while IFS=',' read -r share_host share_index; do
      [[ -z "${share_host}" || -z "${share_index}" ]] && continue
      local share_dir="${HOME}/Desktop/share/${share_index}"
      local share_samba="//GUEST:@${share_host}/share-${share_index}"
      mkdir -p "${share_dir}"
      if [[ ! -d "${share_dir}/tmp" ]]; then
        echo -n "Mounting [${share_samba}] ... "
        diskutil unmount force "${share_dir}" &>/dev/null
        if mount_smbfs -o soft,nodatacache "${share_samba}" "${share_dir}"; then
          echo "done"
        else
          echo "failed"
          result=1
        fi
      else
        echo "Mount [${share_dir}] already"
      fi
    done <"${MEDIA_SHARES_FILE}"
  fi
  return ${result}
}

mount_active() {
  local mountpoint="${1}"
  mount | grep -qE " on ${mountpoint} " && ls "${mountpoint}" >/dev/null 2>&1
}

mount_linux() {
  local result=0
  local mountpoint fstype
  while read -r _dev mountpoint fstype _opts _dump _pass; do
    [[ "${mountpoint}" == /share/* ]] || continue
    if mount_active "${mountpoint}"; then
      echo "Mount [${mountpoint}] already"
      continue
    fi
    echo -n "Mounting [${mountpoint}] ... "
    if [ "${fstype}" == "cifs" ]; then
      ls "${mountpoint}" >/dev/null 2>&1
    else
      mount "${mountpoint}" >/dev/null 2>&1
    fi
    if mount_active "${mountpoint}"; then
      echo "done"
    else
      echo "failed"
      result=1
    fi
  done < <(grep -v '^#' /etc/fstab)
  return ${result}
}

command_mount() {
  if [ "$(uname)" = "Darwin" ]; then
    mount_darwin
  else
    mount_linux
  fi
}

command_home() {
  echo "${ROOT_DIR}"
}

run_stage() {
  case "${1}" in
  stow) command_stow "${PUBLISH_SCOPE}" ;;
  process) command_process ;;
  refresh) command_refresh ;;
  normalise) dispatch_library normalise "" ;;
  analyse) command_analyse ;;
  space) command_space ;;
  *)
    in_list "${1}" "${MEDIA_ACTIONS[@]}" || refuse "unknown stage [${1}]"
    dispatch_action "${1}"
    ;;
  esac
}

run_pipeline() {
  local result=0 stage status
  for stage in "$@"; do
    echo -n "==> $(printf '%-10s' "${stage}") "
    run_stage "${stage}"
    status=$?
    if [ ${status} -eq 0 ]; then
      echo "done"
    else
      [ ${result} -eq 0 ] && result=${status}
      echo "failed"
      if [ "${OPT_PERSISTENT}" -ne 1 ]; then
        echo "amedia pipeline stopped at [${stage}], exit [${result}]" >&2
        return ${result}
      fi
    fi
  done
  [ ${result} -ne 0 ] && echo "amedia pipeline failed, exit [${result}]" >&2
  return ${result}
}

command_publish() {
  PUBLISH_SCOPE="${1:-${MEDIA_SCOPE_DEFAULT}}"
  run_pipeline stow process merge refresh
}

command_process() {
  run_pipeline normalise analyse rename check upscale reformat transcode downscale analyse space
}

parse_args() {
  COMMAND="${1:-help}"
  [ $# -gt 0 ] && shift
  while [ $# -gt 0 ]; do
    case "${1}" in
    --*)
      in_list "${1}" --force --persistent --share --quiet --verbose --dryrun ||
        refuse "unknown option [${1}]"
      command_accepts_option "${COMMAND}" "${1}" ||
        refuse "option [${1}] is not accepted by command [${COMMAND}]"
      case "${1}" in
      --force) OPT_FORCE=1 ;;
      --persistent) OPT_PERSISTENT=1 ;;
      --share)
        [ $# -ge 2 ] || refuse "option [--share] requires an index"
        shift
        OPT_SHARE="${1}"
        ;;
      --quiet) OPT_QUIET=1 ;;
      --verbose) OPT_VERBOSE=1 ;;
      --dryrun) OPT_DRY_RUN=1 ;;
      esac
      ;;
    *)
      [ -z "${POSITIONAL}" ] || refuse "unexpected argument [${1}]"
      POSITIONAL="${1}"
      ;;
    esac
    shift
  done
}

command_accepts_option() {
  local command="${1}" option="${2}"
  case "${option}" in
  --force) [ "${command}" = "analyse" ] ;;
  --persistent) in_list "${command}" publish process ;;
  --dryrun) [ "${command}" = "move" ] ;;
  --share) in_list "${command}" analyse process clean normalise ingress space "${MEDIA_ACTIONS[@]}" ;;
  --quiet | --verbose) in_list "${command}" analyse process publish "${MEDIA_ACTIONS[@]}" ;;
  *) return 1 ;;
  esac
}

command_takes_positional() {
  case "${1}" in
  publish | stow | move | clean | normalise | ingress | find) return 0 ;;
  *) return 1 ;;
  esac
}

main() {
  parse_args "$@"
  if [ -n "${POSITIONAL}" ] && ! command_takes_positional "${COMMAND}"; then
    refuse "unexpected argument [${POSITIONAL}]"
  fi
  resolve_extent
  case "${COMMAND}" in
  help)
    usage
    exit 0
    ;;
  publish) command_publish "${POSITIONAL:-${MEDIA_SCOPE_DEFAULT}}" ;;
  process | analyse | refresh | space) run_stage "${COMMAND}" ;;
  clean | normalise) dispatch_library "${COMMAND}" "${POSITIONAL}" ;;
  ingress) command_ingress "${POSITIONAL}" ;;
  stow) command_stow "${POSITIONAL:-${MEDIA_SCOPE_DEFAULT}}" ;;
  move) command_move "${POSITIONAL}" ;;
  truncate) command_truncate ;;
  find) command_find "${POSITIONAL}" ;;
  metadata) command_metadata ;;
  mount) command_mount ;;
  home) command_home ;;
  *)
    in_list "${COMMAND}" "${MEDIA_ACTIONS[@]}" || refuse "unknown command [${COMMAND}]"
    dispatch_action "${COMMAND}"
    ;;
  esac
}

main "$@"
exit $?
