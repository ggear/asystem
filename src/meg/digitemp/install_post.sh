#!/bin/sh

docker exec digitemp /asystem/runtime/mqtt.sh

docker exec digitemp telegraf --debug --once
