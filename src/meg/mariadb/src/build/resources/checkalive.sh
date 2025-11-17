mariadb-admin ping -uroot -p"${MARIADB_ROOT_PASSWORD}" -h "${MARIADB_SERVICE}" -P "${MARIADB_API_PORT}" >/dev/null 2>&1
