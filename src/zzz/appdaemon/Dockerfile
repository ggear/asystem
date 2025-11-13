# NOTES: https://github.com/AppDaemon/appdaemon/releases
FROM acockburn/appdaemon:4.5.12 AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apk update && \
    apk add --upgrade --no-cache bash=5.2.37-r0 && \
    apk add --upgrade --no-cache less=668-r0 && \
    apk add --upgrade --no-cache curl=8.12.1-r1 && \
    apk add --upgrade --no-cache vim=9.1.1105-r0 && \
    apk add --upgrade --no-cache jq=1.7.1-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY src/main/python/. /asystem/bin/python
COPY target/package/main/resources/image/. /asystem/etc

FROM image_base AS image_build

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["/usr/src/app/dockerStart.sh"]
