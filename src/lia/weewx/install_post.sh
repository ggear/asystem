#!/bin/bash

docker exec weewx weectl device --clear-memory -y
docker exec weewx /data/mqtt.sh
