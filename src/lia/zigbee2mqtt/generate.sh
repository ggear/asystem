#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

VERSION=Z-Stack_3.x.0_coordinator_20230507
pull_repo "${ROOT_DIR}" "${1}" zigbee2mqtt z-stack-firmware koenkk/z-stack-firmware "${VERSION}"
