init_user_database() {
  local user="$1"
  local password="$2"
  local database="$3"

  if [ -z "${user}" ] || [ -z "${database}" ]; then
    echo "Skipping bootstrap entry because user or database is empty (user='${user}', database='${database}')"
    return
  fi

  local user_quoted database_quoted user_lit database_lit password_lit
  user_quoted=$(printf '%s' "${user}" | sed 's/"/""/g')
  database_quoted=$(printf '%s' "${database}" | sed 's/"/""/g')
  user_lit=$(printf '%s' "${user}" | sed "s/'/''/g")
  database_lit=$(printf '%s' "${database}" | sed "s/'/''/g")
  password_lit=$(printf '%s' "${password}" | sed "s/'/''/g")

  local psql_su="psql -h ${POSTGRES_SERVICE} -p ${POSTGRES_API_PORT} -U ${POSTGRES_USER} -d postgres -w"

  local role_exists db_exists
  role_exists=$(${psql_su} -tA -c "SELECT 1 FROM pg_roles WHERE rolname = '${user_lit}' LIMIT 1")
  if [ "${role_exists}" != "1" ]; then
    if [ -n "${password}" ]; then
      ${psql_su} -t -c "CREATE USER \"${user_quoted}\" WITH PASSWORD '${password_lit}'"
    else
      ${psql_su} -t -c "CREATE USER \"${user_quoted}\""
    fi
  elif [ -n "${password}" ]; then
    ${psql_su} -t -c "ALTER USER \"${user_quoted}\" WITH PASSWORD '${password_lit}'"
  fi

  db_exists=$(${psql_su} -tA -c "SELECT 1 FROM pg_database WHERE datname = '${database_lit}' LIMIT 1")
  if [ "${db_exists}" != "1" ]; then
    ${psql_su} -t -c "CREATE DATABASE \"${database_quoted}\""
  fi

  ${psql_su} -t -c "ALTER DATABASE \"${database_quoted}\" OWNER TO \"${user_quoted}\""

  if [ -n "${password}" ]; then
    local pgpass_file="${HOME}/.pgpass"
    touch "${pgpass_file}"
    chmod 600 "${pgpass_file}"
    grep -v "^${POSTGRES_SERVICE}:${POSTGRES_API_PORT}:[^:]*:${user}:" "${pgpass_file}" >"${pgpass_file}.tmp" && mv "${pgpass_file}.tmp" "${pgpass_file}"
    echo "${POSTGRES_SERVICE}:${POSTGRES_API_PORT}:*:${user}:${password}" >>"${pgpass_file}"
  fi
}

init_user_database "${POSTGRES_USER_HASS}" "${POSTGRES_KEY_HASS}" "${POSTGRES_DATABASE_HASS}"
init_user_database "${POSTGRES_USER_MLFLOW}" "${POSTGRES_KEY_MLFLOW}" "${POSTGRES_DATABASE_MLFLOW}"
init_user_database "${POSTGRES_USER_WRANGLE}" "${POSTGRES_KEY_WRANGLE}" "${POSTGRES_DATABASE_WRANGLE}"
