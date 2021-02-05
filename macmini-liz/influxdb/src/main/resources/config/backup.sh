#!/bin/sh

. /root/.influxdbv2/.profile

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

influx backup -b asystem /root/.influxdbv2/backup/${TIMESTAMP} -t $INFLUXDB_TOKEN
influx backup -b hosts /root/.influxdbv2/backup/${TIMESTAMP} -t $INFLUXDB_TOKEN


influx delete -org home --bucket asystem --predicate '_measurement="fx"' --start '1970-01-01T00:00:00Z'  --stop $(date +"%Y-%m-%dT%H:%M:%SZ")
