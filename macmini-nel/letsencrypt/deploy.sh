#!/bin/sh

HOSTS_STRING=$(basename $(dirname $(pwd)))
HOSTS_ARRAY=(${HOSTS_STRING//_/ })
HOST=${HOSTS_ARRAY[0]}

ssh root@${HOST} 'echo "" >>/root/install/macmini-nel/letsencrypt/latest/letsencrypt/live/janeandgraham.com/privkey.pem'
