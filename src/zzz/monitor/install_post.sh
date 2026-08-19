#!/bin/bash

printf "Entity Metadata publish script [monitor] publishing data topics:\n"

docker exec monitor telegraf --debug --once
