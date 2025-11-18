#!/bin/bash

DIR_BACKUP="/var/lib/postgresql/data/backup"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

for SCHEMA in "all"; do
  DIR="${DIR_BACKUP}/${TIMESTAMP}/${SCHEMA}"
  mkdir -p "${DIR}"
  cd "${DIR}"
  echo -n "Starting backup for timestamp [$TIMESTAMP] to [${DIR}] ... "
  pg_dumpall -U postgres | gzip > "all_${TIMESTAMP}.sql.gz"
  echo "done"
done
find "${DIR_BACKUP}" -depth -empty -delete -type d
