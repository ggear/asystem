#!/bin/sh

CONTAINER=cloudflare-ddns

if podman container exists "${CONTAINER}"; then
  podman start "${CONTAINER}"
else
  podman run -i -d --rm \
    --net=host \
    --name "${CONTAINER}" \
    --security-opt=no-new-privileges \
    -v /mnt/data/cloudflare-ddns/config.json:/config.json \
    timothyjmiller/cloudflare-ddns:latest
fi
