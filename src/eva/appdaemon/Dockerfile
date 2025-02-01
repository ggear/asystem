# Notes: https://github.com/AppDaemon/appdaemon/releases
FROM acockburn/appdaemon:4.4.2 AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apk update && \
    apk add --upgrade --no-cache bash=5.2.15-r0 && \
    apk add --upgrade --no-cache less=608-r1 && \
    apk add --upgrade --no-cache curl=8.9.0-r0 && \
    apk add --upgrade --no-cache vim=9.0.0999-r0 && \
    apk add --upgrade --no-cache jq=1.6-r2 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build

FROM image_build AS image_runtime
ENTRYPOINT ["/usr/src/app/dockerStart.sh"]
