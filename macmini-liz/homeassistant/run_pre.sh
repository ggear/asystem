#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

# find postgres by looping over hosts (see pushcerts.sh)
# create user/passwrod/db via ssh
# backup to datbase to home

# ssh macmini-liz "echo 'SELECT '\''CREATE USER haas'\'' WHERE NOT EXISTS (SELECT FROM pg_user WHERE usename = '\''haas'\'')\gexec' | docker exec -i postgres psql -U asystem -d asystem"
# ssh macmini-liz "echo 'ALTER USER haas WITH PASSWORD '\''haas'\''\;' | docker exec -i postgres psql -U asystem -d asystem"
# ssh macmini-liz "echo 'SELECT '\''CREATE DATABASE haas'\'' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '\''haas'\'')\gexec' | docker exec -i postgres psql -U asystem -d asystem"
# ssh macmini-liz "docker exec -i postgres pg_dump -U asystem -d asystem > /tmp/haas.bak"