#!/bin/sh

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
for BUCKET in ${INFLUXDB_BUCKET_HOME_PRIVATE}; do
  DIR="/var/lib/influxdb2/backup/${TIMESTAMP}/${BUCKET}"
  mkdir -p ${DIR}
  influx backup -b ${BUCKET} ${DIR} -t ${INFLUXDB_TOKEN}
  echo "Completed backup for timestamp [$TIMESTAMP] to [${DIR}]"
done
