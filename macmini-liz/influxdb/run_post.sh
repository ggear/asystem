#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
. config/.profile

# TODO: Create buckets (host/asystem) if not exist, get IDs, create DBRPS in this script
#curl -XPOST http://localhost:8086/api/v2/dbrps \
#  -H "Authorization: Token ${INFLUXDB_TOKEN}" \
#  -H 'Content-type: application/json' \
#  -d '{
#        "organization": "home",
#        "bucket_id": "ace73b34f9f08175",
#        "database": "asystem",
#        "retention_policy": "autogen",
#        "default": true
#      }'
