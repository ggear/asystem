#!/bin/sh

docker exec weewx /home/weewx/bin/wee_device /home/weewx/weewx.conf --clear-memory -y
docker exec weewx /data/mqtt.sh
