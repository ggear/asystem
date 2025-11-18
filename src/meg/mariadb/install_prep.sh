#!/bin/bash

docker exec --user root mariadb /var/lib/influxdb2/backup.sh
