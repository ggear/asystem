#!/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! pg_isready -q -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -t 1 >>/dev/null 2>&1; do
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
if [ $(psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "SELECT usename FROM pg_user WHERE usename = '"${POSTGRES_USER_HAAS}"'" | grep ${POSTGRES_USER_HAAS} | wc -l) -eq 0 ]; then
  psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "CREATE USER ${POSTGRES_USER_HAAS}"
  psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "ALTER USER ${POSTGRES_USER_HAAS} WITH PASSWORD '"${POSTGRES_KEY_HAAS}"'"
fi
if [ $(psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "SELECT datname FROM pg_database WHERE datname = '"${POSTGRES_DATABASE_HAAS}"'" | grep ${POSTGRES_DATABASE_HAAS} | wc -l) -eq 0 ]; then
  psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -w -t -c "CREATE DATABASE ${POSTGRES_DATABASE_HAAS}"
fi

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
