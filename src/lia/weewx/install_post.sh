#!/bin/sh

docker exec weewx /home/weewx/bin/weectl device /home/weewx/weewx.conf --clear-memory -y
docker exec weewx /data/mqtt.sh
