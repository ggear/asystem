# NOTES: https://sabnzbd.org/downloads#
FROM linuxserver/sabnzbd:5.1.2 AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=5.3.9-r1 && \
    apk add --upgrade --no-cache coreutils=9.11-r0 && \
    apk add --upgrade --no-cache less=702-r0 && \
    apk add --upgrade --no-cache curl=8.21.0-r0 && \
    apk add --upgrade --no-cache vim=9.2.0854-r0 && \
    apk add --upgrade --no-cache jq=1.8.1-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base

FROM image_base AS image_build
COPY target/package/main/resources/image/. /asystem/etc

FROM image_build AS image_runtime
WORKDIR /asystem/etc
