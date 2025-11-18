/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  mariadb -u"${MARIADB_USER}" -p"${MARIADB_PASSWORD}" -h "${MARIADB_SERVICE}" -P "${MARIADB_API_PORT}" -e "SELECT 1;" >/dev/null 2>&1
