#!/bin/sh

set -o nounset
set -o errexit

[ ! -f /data/html/index.html ] && mkdir -p /data/html && touch /data/html/index.html
service apache2 start

[ ! -f /data/weewx.conf ] && cp -f /home/weewx/weewx.conf /data

weewxd "$@"
