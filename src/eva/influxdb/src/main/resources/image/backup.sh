#!/bin/bash

DIR_BACKUP="/var/lib/influxdb2/backup"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

influx config set --config-name remote
for BUCKET in ${INFLUXDB_BUCKET_HOME_PRIVATE}; do
  DIR="${DIR_BACKUP}/${TIMESTAMP}/${BUCKET}"
  mkdir -p ${DIR}
  influx backup -b ${BUCKET} ${DIR} -t ${INFLUXDB_TOKEN}
  echo "Completed backup for timestamp [$TIMESTAMP] to [${DIR}]"
done
find ${DIR_BACKUP} -depth -empty -delete -type d
