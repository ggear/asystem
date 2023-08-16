#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"

ssh root@${HOST} docker exec -e WRANGLE_ENABLE_DATA_TRUNC=false -e WRANGLE_DISABLE_DATA_DELTA=true --user root wrangle telegraf --debug --once
