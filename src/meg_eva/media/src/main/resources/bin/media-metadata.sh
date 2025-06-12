#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

DEFAULTS_FILE=""
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  if [ "$(basename "$(dirname "$(pwd)")")" == "movies" ] || [ "$(basename "$(dirname "$(dirname "$(pwd)")")")" == "series" ]; then
    DEFAULTS_FILE="._defaults.yaml"
  fi
fi
if [ -n "${DEFAULTS_FILE}" ]; then
  if [ ! -f "${DEFAULTS_FILE}" ]; then
    cat >"${DEFAULTS_FILE}" <<EOF
#- transcode_action: Ignore
#- target_quality: 6
#- target_channels: 2
#- target_lang: eng
#- native_lang: eng
EOF
  fi
  echo "" && echo "Metadata file:" && cat ._metadata_*.yaml
  echo "" && echo "Defaults file:" && cat "${DEFAULTS_FILE}"
  echo "" && echo "vi ${DEFAULTS_FILE}"
  echo ""
else
  echo "Not in media file root directory, not doing anything!"
fi
