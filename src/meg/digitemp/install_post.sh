#!/bin/sh

docker exec digitemp /asystem/runtime/mqtt.sh

printf "Entity Metadata publish script sleeping before running for first time ... " && sleep 2 && printf "done\n\n"
printf "Entity Metadata publish script publishing data:\n"
docker exec digitemp telegraf --debug --once
printf "Entity Metadata publish script publishing data complete\n"
