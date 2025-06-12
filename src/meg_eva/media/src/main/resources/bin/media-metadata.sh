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
  if [ ! -f "${DEFAULTS_FILE}" ] || [ $(grep "Generated defaults" "${DEFAULTS_FILE}" | wc -l) -eq 0 ]; then
    cat >>"${DEFAULTS_FILE}" <<EOF
# Generated defaults V1
#- transcode_action: Ignore
#- target_quality: 6
#- target_channels: 2
#- target_lang: eng
#- native_lang: eng
EOF
  fi
  echo "" && echo "Metadata file:" && cat ._metadata_*.yaml
  echo "" && echo "Defaults file: vi ${DEFAULTS_FILE}"
  echo ""
else
  echo "Not in media file root directory, not doing anything!"
fi
