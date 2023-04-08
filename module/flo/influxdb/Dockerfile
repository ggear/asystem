# https://docs.influxdata.com/influxdb/latest/reference/release-notes/influxdb
FROM influxdb:2.7.0-alpine as image_base

FROM image_base as image_package
USER root
RUN apk add --no-cache jq==1.6-r2
RUN apk add --no-cache curl==7.88.1-r1
RUN apk add --no-cache netcat-openbsd==1.130-r4

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
