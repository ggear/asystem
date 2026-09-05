#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

SERVICE_WAIT_ALIVE_SECONDS=900
SERVICE_WAIT_EXECUTING_SECONDS=900

wait_service() {
  local script="$1" label="$2" interval="$3" timeout="$4" waited=0
  ((interval > 0)) || interval=1
  while ! "${ASYSTEM_HOME}/${script}" >/dev/null 2>&1; do
    if ((waited >= timeout)); then
      echo "Waiting for service to ${label} ... failed after [${waited}] of [${timeout}] seconds"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 5
      echo "ERROR: Service failed to ${label} within [${timeout}] seconds" >&2
      exit 1
    fi
    if ((waited % 30 == 0)); then
      echo "Waiting for service to ${label} ... waited [${waited}] of [${timeout}] seconds"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 3
    fi
    sleep "${interval}"
    waited=$((waited + interval))
  done
  echo "Waiting for service to ${label} ... done after [${waited}] of [${timeout}] seconds"
}

wait_service "checkalive.sh" "come alive" 1 "${SERVICE_WAIT_ALIVE_SECONDS}"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

bash#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

MESSAGE="Waiting for service to come alive ... "
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkalive.sh"; do
  echo "${MESSAGE}" && sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

psql_su() {
  PGPASSWORD="${PGPASSWORD}" psql -h "${POSTGRES_SERVICE}" -p "${POSTGRES_API_PORT}" -U "${POSTGRES_USER}" -d postgres "$@"
}

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

  local role_exists db_exists
  role_exists=$(psql_su -tA -c "SELECT 1 FROM pg_roles WHERE rolname = '${user_lit}' LIMIT 1")
  if [ "${role_exists}" != "1" ]; then
    if [ -n "${password}" ]; then
      psql_su -t -c "CREATE USER \"${user_quoted}\" WITH PASSWORD '${password_lit}'"
    else
      psql_su -t -c "CREATE USER \"${user_quoted}\""
    fi
  elif [ -n "${password}" ]; then
    psql_su -t -c "ALTER USER \"${user_quoted}\" WITH PASSWORD '${password_lit}'"
  fi

  db_exists=$(psql_su -tA -c "SELECT 1 FROM pg_database WHERE datname = '${database_lit}' LIMIT 1")
  if [ "${db_exists}" != "1" ]; then
    psql_su -t -c "CREATE DATABASE \"${database_quoted}\""
  fi

  psql_su -t -c "ALTER DATABASE \"${database_quoted}\" OWNER TO \"${user_quoted}\""
}

init_user_database "${POSTGRES_USER_HASS}" "${POSTGRES_KEY_HASS}" "${POSTGRES_DATABASE_HASS}"
init_user_database "${POSTGRES_USER_MLFLOW}" "${POSTGRES_KEY_MLFLOW}" "${POSTGRES_DATABASE_MLFLOW}"
init_user_database "${POSTGRES_USER_WRANGLE}" "${POSTGRES_KEY_WRANGLE}" "${POSTGRES_DATABASE_WRANGLE}"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

wait_service "checkexecuting.sh" "start executing" 1 "${SERVICE_WAIT_EXECUTING_SECONDS}"
echo "----------" && echo "✅ Service has started"