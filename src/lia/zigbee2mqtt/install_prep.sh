#!/bin/bash

docker exec zigbee2mqtt /asystem/etc/mqtt.sh
rm -rf /root/home/zigbee2mqtt/latest/log/*
