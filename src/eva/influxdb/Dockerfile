# Notes: https://github.com/influxdata/influxdb/releases
FROM influxdb:2.7.11-alpine AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apk update && \
    apk add --upgrade --no-cache bash=5.2.26-r0 && \
    apk add --upgrade --no-cache less=643-r2 && \
    apk add --upgrade --no-cache curl=8.12.1-r0 && \
    apk add --upgrade --no-cache vim=9.1.0707-r0 && \
    apk add --upgrade --no-cache jq=1.7.1-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build

FROM image_base AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
