#!/bin/bash

chmod +x /home/asystem/weewx/latest/mqtt.sh
docker exec weewx weectl device --clear-memory -y
docker exec weewx /asystem/mnt/mqtt.sh
