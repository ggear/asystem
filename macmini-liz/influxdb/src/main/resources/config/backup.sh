#!/bin/sh

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

influx backup -b asystem /root/.influxdbv2/backup/${TIMESTAMP} -t $INFLUXDB_TOKEN
influx backup -b hosts /root/.influxdbv2/backup/${TIMESTAMP} -t $INFLUXDB_TOKEN
