#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

# find postgres by looping over hosts (see pushcerts.sh)
# create user/passwrod/db via ssh
# backup to datbase to home

cd "${SERVICE_INSTALL}" || exit
if [ -f "${SERVICE_INSTALL}/hosts" ]; then
  while read -r host; do
    POSTGRES_HOME=$(ssh -q -n -o "StrictHostKeyChecking=no" root@${host} \
      "find /home/asystem/postgres -maxdepth 1 -mindepth 1 2>/dev/null | sort | tail -n 1")
    POSTGRES_INSTALL=$(ssh -q -n -o "StrictHostKeyChecking=no" root@${host} \
      "find /var/lib/asystem/install/\$(hostname)/postgres -maxdepth 1 -mindepth 1 2>/dev/null | sort | tail -n 1")
    if [ -n "${POSTGRES_HOME}" ] && [ -n "${POSTGRES_INSTALL}" ]; then
      ssh -qno "StrictHostKeyChecking=no" ${host} "echo 'SELECT '\''CREATE USER haas'\'' WHERE NOT EXISTS (SELECT FROM pg_user WHERE usename = '\''haas'\'')\gexec' | docker exec -i postgres psql -U asystem -d asystem"
      ssh -qno "StrictHostKeyChecking=no" ${host} "echo 'ALTER USER haas WITH PASSWORD '\''haas'\''\;' | docker exec -i postgres psql -U asystem -d asystem" >/dev/null
      ssh -qno "StrictHostKeyChecking=no" ${host} "echo 'SELECT '\''CREATE DATABASE haas'\'' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '\''haas'\'')\gexec' | docker exec -i postgres psql -U asystem -d asystem"
      ssh -qno "StrictHostKeyChecking=no" ${host} "docker exec -i postgres pg_dump -U asystem -d asystem" >db_backup.sql
    fi
  done <"${SERVICE_INSTALL}/hosts"
fi
