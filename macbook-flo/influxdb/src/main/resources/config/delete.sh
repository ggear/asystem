#!/bin/sh

for MEASUREMENT in media_player; do
    influx delete --org ${INFLUXDB_ORG} --bucket ${INFLUXDB_BUCKET_HOME_PRIVATE} --predicate '_measurement="'${MEASUREMENT}'"' --start '1970-01-01T00:00:00Z' --stop $(date +"%Y-%m-%dT%H:%M:%SZ") -t ${INFLUXDB_TOKEN}
done

for MEASUREMENT in currency interest weather; do
    influx delete --org ${INFLUXDB_ORG} --bucket ${INFLUXDB_BUCKET_DATA_PUBLIC} --predicate '_measurement="'${MEASUREMENT}'"' --start '1970-01-01T00:00:00Z' --stop $(date +"%Y-%m-%dT%H:%M:%SZ") -t ${INFLUXDB_TOKEN}
done

for MEASUREMENT in equity health; do
    influx delete --org ${INFLUXDB_ORG} --bucket ${INFLUXDB_BUCKET_DATA_PRIVATE} --predicate '_measurement="'${MEASUREMENT}'"' --start '1970-01-01T00:00:00Z' --stop $(date +"%Y-%m-%dT%H:%M:%SZ") -t ${INFLUXDB_TOKEN}
done
