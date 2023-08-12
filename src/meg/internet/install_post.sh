#!/bin/sh

docker exec internet /asystem/runtime/mqtt.sh

printf "Entity Metadata publish script [internet] sleeping before publishing data topics ... " && sleep 2 && printf "done\n\nEntity Metadata publish script [internet] publishing data topics:\n"

docker exec internet telegraf --debug --once
