#!/bin/sh

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

influx backup -b asystem /var/lib/influxdb2/backup/${TIMESTAMP} -t $INFLUXDB_TOKEN
influx backup -b hosts /var/lib/influxdb2/backup/${TIMESTAMP} -t $INFLUXDB_TOKEN
