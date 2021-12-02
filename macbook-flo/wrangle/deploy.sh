#!/bin/sh

ssh root@macbook-flo docker exec -e WRANGLE_REPROCESS_ALL_FILES=true wrangle telegraf --debug --once
