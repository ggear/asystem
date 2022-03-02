#!/bin/sh

/letsencrypt/live/janeandgraham.com/privkey.pem

ssh root@macbook-flo docker exec -e WRANGLE_REPROCESS_ALL_FILES=true wrangle telegraf --debug --once
