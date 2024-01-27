#!/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! pg_isready -q -h ${POSTGRES_IP} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -t 1 >/dev/null 2>&1; do
  echo "Waiting for service to come up ..." && sleep 1
done

set -e
set -o pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

#######################################################################################
# Home Assistant
#######################################################################################
PGPASSWORD=${POSTGRES_KEY}
if [ $(psql -h ${POSTGRES_IP} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "SELECT usename FROM pg_user WHERE usename = '"${POSTGRES_USER_HASS}"'" | grep ${POSTGRES_USER_HASS} | wc -l) -eq 0 ]; then
  psql -h ${POSTGRES_IP} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "CREATE USER ${POSTGRES_USER_HASS}"
  psql -h ${POSTGRES_IP} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "ALTER USER ${POSTGRES_USER_HASS} WITH PASSWORD '"${POSTGRES_KEY_HASS}"'"
fi
if [ $(psql -h ${POSTGRES_IP} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "SELECT datname FROM pg_database WHERE datname = '"${POSTGRES_DATABASE_HASS}"'" | grep ${POSTGRES_DATABASE_HASS} | wc -l) -eq 0 ]; then
  psql -h ${POSTGRES_IP} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "CREATE DATABASE ${POSTGRES_DATABASE_HASS}"
fi

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
