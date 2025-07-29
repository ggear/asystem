#!/bin/bash

docker exec monitor /asystem/etc/mqtt.sh

printf "Entity Metadata publish script [monitor] sleeping before publishing data topics ... " && sleep 2 && printf "done\n\nEntity Metadata publish script [monitor] publishing data topics:\n"

docker exec monitor telegraf --debug --once
