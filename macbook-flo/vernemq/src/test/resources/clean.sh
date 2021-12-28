#!/bin/sh

mosquitto_sub -h macmini-liz -p 1883 -W 1 -v -t dev/anode/status
mosquitto_sub -h macmini-liz -p 1883 -W 1 -v -t dev/haas/sensor/config/#
mosquitto_sub -h macmini-liz -p 1883 -v -t dev/haas/sensor/state/#
