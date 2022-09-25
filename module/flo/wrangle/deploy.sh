#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"

ssh root@${HOST} docker exec -e WRANGLE_ENABLE_DATA_TRUNC=true -e WRANGLE_DISABLE_DATA_DELTA=true --user root wrangle telegraf --debug --once
