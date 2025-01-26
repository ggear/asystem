#!/bin/bash

if STATUS="$(curl -sf --connect-timeout 2 --max-time 2 "http://${SABNZBD_SERVICE_PROD}:${SABNZBD_HTTP_PORT}/sabnzbd/api?output=json&apikey=${SABNZBD_API_KEY}&mode=status&skip_dashboard=0")" && [ "$(jq -er ".status.paused" <<<"${STATUS}")" == "false" ] && [ "$(jq -er "[.status.servers[].serveractiveconn] | add" <<<"${STATUS}")" -gt 0 ]; then exit 0; else exit 1; fi
