#!/bin/sh

ssh root@macmini-liz docker exec -e WRANGLE_REPROCESS_ALL_FILES=true wrangle telegraf --debug --once
