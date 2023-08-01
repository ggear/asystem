#!/bin/sh

docker exec internet /asystem/runtime/mqtt.sh

printf "Entity Metadata publish script sleeping before publishing data ... " && sleep 2 && printf "done\n\nEntity Metadata publish script publishing data:\n"
docker exec internet telegraf --debug --once
