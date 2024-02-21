#!/bin/sh

DIR_BACKUP="/var/lib/influxdb2/backup"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
for BUCKET in ${INFLUXDB_BUCKET_HOME_PRIVATE}; do
  DIR="${DIR_BACKUP}/${TIMESTAMP}/${BUCKET}"
  mkdir -p ${DIR}
  influx backup -b ${BUCKET} ${DIR} -t ${INFLUXDB_TOKEN} --host ${INFLUXDB_SERVICE}
  echo "Completed backup for timestamp [$TIMESTAMP] to [${DIR}]"
done
find ${DIR_BACKUP} -depth -empty -delete -type d
