# https://github.com/influxdata/influxdb/releases
FROM influxdb:2.7.10-alpine AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apk update && \
    apk add --no-cache bash=5.2.26-r0 && \
    apk add --no-cache less=643-r2 && \
    apk add --no-cache curl=8.11.0-r2 && \
    apk add --no-cache vim=9.1.0707-r0 && \
    apk add --no-cache jq=1.7.1-r0 && \
    apk cache clean && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build

FROM image_base AS image_runtime
ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
