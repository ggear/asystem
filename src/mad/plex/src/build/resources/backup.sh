PLEX_BACKUP_CONFIG="config"
PLEX_BACKUP_CONTAINER="${SERVICE_NAME:?}"
PLEX_BACKUP_INCLUDES=(
  "Library/Application Support/Plex Media Server/Plug-in Support"
  "Library/Application Support/Plex Media Server/Preferences.xml"
)
PLEX_BACKUP_EXCLUDES=(
  "*.db-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
  "Caches"
)

plex_backup_stopped() {
  if docker stop "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1; then
    docker wait "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1 || true
  else
    echo "Stop failed [${PLEX_BACKUP_CONTAINER}], copying the running configuration" >&2
  fi
}

plex_backup_started() {
  [ "${BACKUP_SERVICE_RESTART}" = "true" ] || return 0
  docker start "${PLEX_BACKUP_CONTAINER}" >/dev/null 2>&1 || echo "Start failed [${PLEX_BACKUP_CONTAINER}]" >&2
}

backup_interrupted() {
  plex_backup_started
}

backup_written() {
  local status=0 include exclude excludes=()
  for include in "${PLEX_BACKUP_INCLUDES[@]}"; do
    if [ ! -e "${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}/${include}" ]; then
      echo "Declared path [${include}] is absent from [${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}]" >&2
      return 1
    fi
  done
  for exclude in "${PLEX_BACKUP_EXCLUDES[@]}"; do
    excludes+=("--exclude=${exclude}")
  done
  backup_target "${BACKUP_FULL_SUFFIX}" "tar.gz" || return 1
  plex_backup_stopped
  tar --create --directory "${BACKUP_SOURCE_PATH}/${PLEX_BACKUP_CONFIG}" --numeric-owner --preserve-permissions \
    "${excludes[@]}" --file - -- "${PLEX_BACKUP_INCLUDES[@]}" 2>/dev/null | gzip >"${BACKUP_TARGET_PATH}.tmp" || status=1
  plex_backup_started
  return "${status}"
}
