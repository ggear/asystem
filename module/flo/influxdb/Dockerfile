# https://github.com/influxdata/influxdb/releases
FROM influxdb:2.3.0-alpine as image_base

FROM image_base as image_package
USER root
RUN apk add --no-cache \
  jq==1.6-r1 \
  curl==7.79.1-r2 \
  netcat-openbsd==1.130-r2

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
