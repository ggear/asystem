#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/../.env_media"

WORKING_DIR=${1}
if [ ! -d "${WORKING_DIR}" ]; then
  echo "Usage: ${0} <working-dir>"
  exit 1
fi

RESULT=0

run() {
  "$@" || RESULT=1
}

normalise_permissions() {
  local NORMALISE_DIR=${1}
  local DIR_MODE=${2}
  local SCRIPT_MODE=${3}
  local FILE_MODE=${4}
  [ -d "${NORMALISE_DIR}" ] || return
  if command -v setfacl &>/dev/null; then
    run setfacl -bR "${NORMALISE_DIR}"
  fi
  if id "graham" &>/dev/null && getent group "users" &>/dev/null; then
    ${FIND_CMD} "${NORMALISE_DIR}" -exec chown "graham:users" {} \; || RESULT=1
  fi
  ${FIND_CMD} "${NORMALISE_DIR}" -type d -exec chmod "${DIR_MODE}" {} \; || RESULT=1
  ${FIND_CMD} "${NORMALISE_DIR}" -type f -name "*.sh" -exec chmod "${SCRIPT_MODE}" {} \; || RESULT=1
  ${FIND_CMD} "${NORMALISE_DIR}" -type f ! -name "*.sh" -exec chmod "${FILE_MODE}" {} \; || RESULT=1
}

share_tmp_scripts_dir() {
  for _SHARE_DIR in ${SHARE_DIRS}; do
    [[ "${WORKING_DIR}" == "${_SHARE_DIR}" || "${WORKING_DIR}" == "${_SHARE_DIR}/"* ]] && {
      echo "${_SHARE_DIR}/tmp/scripts"
      return
    }
  done
}

echo -n "Normalising '${WORKING_DIR}' ... "
if [ "$(uname)" == "Linux" ]; then
  normalise_permissions "${WORKING_DIR}" 750 750 640
  SHARE_DIR_TMP=$(share_tmp_scripts_dir)
  if [ -n "${SHARE_DIR_TMP}" ]; then
    run mkdir -p "${SHARE_DIR_TMP}"
    normalise_permissions "${SHARE_DIR_TMP}" 770 770 660
  fi
fi
${FIND_CMD} "${WORKING_DIR}" -type f -name nohup -exec rm -f {} \; || RESULT=1
${FIND_CMD} "${WORKING_DIR}" -type f -name .DS_Store -exec rm -f {} \; || RESULT=1
${FIND_CMD} "${WORKING_DIR}" -type f -regextype posix-extended -regex '.*/\.[^/]*\.[A-Za-z0-9]{6}$' -exec rm -f {} \; || RESULT=1
if [ ${RESULT} -ne 0 ]; then
  echo "failed"
  exit 1
fi
echo "done"
exit 0
