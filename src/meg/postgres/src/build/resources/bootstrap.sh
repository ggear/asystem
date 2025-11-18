init_user_database() {
  if [ $(psql -h ${POSTGRES_SERVICE} -p ${POSTGRES_API_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "SELECT usename FROM pg_user WHERE usename = '"$1"'" | grep $1 | wc -l) -eq 0 ]; then
    psql -h ${POSTGRES_SERVICE} -p ${POSTGRES_API_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "CREATE USER $1"
    psql -h ${POSTGRES_SERVICE} -p ${POSTGRES_API_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "ALTER USER $1 WITH PASSWORD '"$2"'"
  fi
  if [ $(psql -h ${POSTGRES_SERVICE} -p ${POSTGRES_API_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "SELECT datname FROM pg_database WHERE datname = '"$3"'" | grep $3 | wc -l) -eq 0 ]; then
    psql -h ${POSTGRES_SERVICE} -p ${POSTGRES_API_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "CREATE DATABASE $3"
  fi
}

init_user_database "${POSTGRES_USER_HASS}" "${POSTGRES_KEY_HASS}" "${POSTGRES_DATABASE_HASS}"
init_user_database "${POSTGRES_USER_MLFLOW}" "${POSTGRES_KEY_MLFLOW}" "${POSTGRES_DATABASE_MLFLOW}"
