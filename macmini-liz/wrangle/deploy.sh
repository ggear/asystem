#!/bin/sh

ssh root@macmini-liz docker exec -e WRANGLE_REPROCESS_ALL_FILES=false wrangle telegraf --debug --once
