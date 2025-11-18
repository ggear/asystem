/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  mariadb -uroot -p"${MARIADB_ROOT_PASSWORD}" -h "${MARIADB_SERVICE}" -P "${MARIADB_API_PORT}" -e "SELECT 1;" >/dev/null 2>&1
