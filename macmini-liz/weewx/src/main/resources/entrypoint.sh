#!/bin/sh

set -o nounset
set -o errexit

service rsyslog start
service apache2 start

/home/weewx/bin/weewxd "$@"
