#!/bin/bash

DIR_BACKUP="/var/lib/mysql/backup"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

for SCHEMA in "all"; do
  DIR="${DIR_BACKUP}/${TIMESTAMP}/${SCHEMA}"
  mkdir -p "${DIR}"
  cd "${DIR}"
  echo -n "Starting backup for timestamp [$TIMESTAMP] to [${DIR}] ... "
  mariadb-dump -uroot -p"${MARIADB_ROOT_PASSWORD}" --all-databases --single-transaction --quick | gzip >"all_${TIMESTAMP}.sql.gz"
  echo "done"
done
find "${DIR_BACKUP}" -depth -empty -delete -type d
