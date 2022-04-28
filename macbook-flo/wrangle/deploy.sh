#!/bin/sh

HOSTS_STRING=$(basename $(dirname $(pwd)))
HOSTS_ARRAY=(${HOSTS_STRING//_/ })
HOST=$(basename $(dirname $PWD))

ssh root@${HOST} docker exec -e WRANGLE_REPROCESS_ALL_FILES=true --user root wrangle telegraf --debug --once
