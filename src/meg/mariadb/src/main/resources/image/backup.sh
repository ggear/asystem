#!/bin/bash

DIR_BACKUP="/var/lib/mysql/backup"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

for SCHEMA in "all"; do
  DIR="${DIR_BACKUP}/${TIMESTAMP}/${SCHEMA}"
  mkdir -p "${DIR}"
  cd "${DIR}"
  mariadb-dump -uroot -p"${MARIADB_ROOT_PASSWORD}" --all-databases --single-transaction --quick | gzip >"all_${TIMESTAMP}.sql.gz"
  echo "Completed backup for timestamp [$TIMESTAMP] to [${DIR}]"
done
find "${DIR_BACKUP}" -depth -empty -delete -type d
