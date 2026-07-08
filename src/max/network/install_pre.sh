#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

. "${SERVICE_INSTALL}/.env"

"${SERVICE_INSTALL}/image/mqtt.sh"
