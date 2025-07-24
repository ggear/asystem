#!/bin/bash

docker exec --user influxdb influxdb /var/lib/influxdb2/backup.sh
