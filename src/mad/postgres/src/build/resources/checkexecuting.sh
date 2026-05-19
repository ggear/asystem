/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  psql -h "${POSTGRES_SERVICE}" -p "${POSTGRES_API_PORT}" -U "${POSTGRES_USER}" -d "postgres" -c "SELECT 1;" >/dev/null 2>&1
