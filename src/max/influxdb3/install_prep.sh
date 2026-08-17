#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker exec -i --user root influxdb3 bash -s <"${SCRIPT_DIR}/image/backup.sh"
