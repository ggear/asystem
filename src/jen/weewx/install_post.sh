#!/bin/bash

docker exec weewx weectl device --clear-memory -y
docker exec weewx /asystem/mnt/mqtt.sh
