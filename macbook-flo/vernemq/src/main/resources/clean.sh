#!/bin/bash

mosquitto_sub -h macbook-flo -p 1883 -t haas/sensor/config/# -W 1 2>/dev/null | while IFS= read -r line; do
  tokens=(${line})
  mosquitto_pub -h macbook-flo -p 1883 -t ${tokens[0]} -n -r -d
done
