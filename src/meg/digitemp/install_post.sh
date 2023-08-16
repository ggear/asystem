#!/bin/sh

docker exec digitemp /asystem/runtime/mqtt.sh

printf "Entity Metadata publish script [digitemp] sleeping before publishing data topics ... " && sleep 2 && printf "done\n\nEntity Metadata publish script [digitemp] publishing data topics:\n"

docker exec digitemp telegraf --debug --once
