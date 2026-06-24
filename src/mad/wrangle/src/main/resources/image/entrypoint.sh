#!/usr/bin/env bash

set -Eeuo pipefail

error() {
  echo "entrypoint.sh: $*" >&2
  exit 2
}

append_value_arg() {
  local env_name=$1
  local flag=$2
  local value=${!env_name:-}

  if [[ -n "${value}" ]]; then
    wrangle_args+=("${flag}" "${value}")
  fi
}

append_bool_arg() {
  local env_name=$1
  local flag=$2
  local value=${!env_name:-}

  if [[ -z "${value}" ]]; then
    return
  fi

  case "${value}" in
  1 | [Tt][Rr][Uu][Ee] | [Yy][Ee][Ss] | [Yy] | [Oo][Nn])
    wrangle_args+=("${flag}")
    ;;
  0 | [Ff][Aa][Ll][Ss][Ee] | [Nn][Oo] | [Nn] | [Oo][Ff][Ff])
    ;;
  *)
    error "${env_name} must be a boolean value, got '${value}'"
    ;;
  esac
}

wrangle_args=(--poll-period "${WRANGLE_POLL_PERIOD:-30}")

append_value_arg WRANGLE_CACHE_DIR --cache-dir
append_value_arg WRANGLE_FILTER_PLUGINS --filter-plugins
append_value_arg WRANGLE_REPO_SCOPE --repo-scope
append_value_arg WRANGLE_LOG --log

append_bool_arg WRANGLE_DISABLE_LOOP --disable-loop
append_bool_arg WRANGLE_FORCE_REPROCESSING --force-reprocessing
append_bool_arg WRANGLE_FORCE_DOWNLOADS --force-downloads

append_bool_arg WRANGLE_ENABLE_DRIVE_UPLOADS --enable-drive-uploads
append_bool_arg WRANGLE_ENABLE_SHEET_UPLOADS --enable-sheet-uploads
append_bool_arg WRANGLE_ENABLE_DATABASE_UPLOADS --enable-database-uploads

append_bool_arg WRANGLE_DISABLE_DRIVE_DOWNLOADS --disable-drive-downloads
append_bool_arg WRANGLE_DISABLE_SOURCE_DOWNLOADS --disable-source-downloads
append_bool_arg WRANGLE_DISABLE_DATABASE_DOWNLOADS --disable-database-downloads
append_bool_arg WRANGLE_DISABLE_SHEET_DOWNLOADS --disable-sheet-downloads

if [[ $# -eq 0 ]]; then
  exec wrangle "${wrangle_args[@]}"
elif [[ "$1" == -* ]]; then
  exec wrangle "${wrangle_args[@]}" "$@"
else
  exec "$@"
fi
