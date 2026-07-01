# NOTES: https://sabnzbd.org/downloads#
FROM linuxserver/sabnzbd:5.0.4 AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=5.3.3-r1 && \
    apk add --upgrade --no-cache coreutils=9.8-r1 && \
    apk add --upgrade --no-cache less=685-r0 && \
    apk add --upgrade --no-cache curl=8.19.0-r0 && \
    apk add --upgrade --no-cache vim=9.2.0481-r0 && \
    apk add --upgrade --no-cache jq=1.8.1-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base

FROM image_base AS image_build
COPY target/package/main/resources/image/. /asystem/etc

FROM image_build AS image_runtime
WORKDIR /asystem/etc
