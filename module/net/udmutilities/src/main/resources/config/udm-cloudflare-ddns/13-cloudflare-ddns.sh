#!/bin/sh

CONTAINER=cloudflare-ddns

podman stop "${CONTAINER}" 2>/dev/null
podman rm "${CONTAINER}" 2>/dev/null
podman create --restart always \
  --name "${CONTAINER}" \
  -e TZ="Australia/Perth" \
  -v "/mnt/data/udm-cloudflare-ddns/config.json:/config.json" \
  --security-opt=no-new-privileges \
  timothyjmiller/cloudflare-ddns:latest
