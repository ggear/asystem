#!/bin/bash

docker exec weewx weectl device --clear-memory -y
docker exec weewx /asystem/etc/mqtt.sh
