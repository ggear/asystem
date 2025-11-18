#!/bin/bash

DIR_BACKUP="/var/lib/postgresql/data/backup"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

for SCHEMA in "all"; do
  DIR="${DIR_BACKUP}/${TIMESTAMP}/${SCHEMA}"
  mkdir -p ${DIR}
  pg_dumpall -U postgres | gzip > all_${TIMESTAMP}.sql.gz
  echo "Completed backup for timestamp [$TIMESTAMP] to [${DIR}]"
done
find ${DIR_BACKUP} -depth -empty -delete -type d
