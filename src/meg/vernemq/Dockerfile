# NOTES: https://github.com/vernemq/vernemq/releases
FROM vernemq/vernemq:2.1.2-alpine AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=5.2.37-r0 && \
    apk add --upgrade --no-cache coreutils=9.7-r1 && \
    apk add --upgrade --no-cache less=679-r0 && \
    apk add --upgrade --no-cache vim=9.1.1566-r0 && \
    apk add --upgrade --no-cache mosquitto-clients=2.0.21-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base

FROM image_base AS image_build

FROM image_build AS image_runtime
COPY target/package/main/resources/image/. /asystem/etc
WORKDIR /asystem/etc
ENTRYPOINT [ "start_vernemq" ]
