#!/bin/sh

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
for BUCKET in ${INFLUXDB_BUCKET_HOME_PRIVATE}; do
  mkdir -p /var/lib/influxdb2/backup/${TIMESTAMP}/${BUCKET}
  influx backup -b ${BUCKET} /var/lib/influxdb2/backup/${TIMESTAMP}/${BUCKET} -t $INFLUXDB_TOKEN
done
