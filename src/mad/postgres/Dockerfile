# https://github.com/timescale/timescaledb/releases
FROM timescale/timescaledb:2.27.2-pg18 AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=5.3.3-r1 && \
    apk add --upgrade --no-cache coreutils=9.8-r1 && \
    apk add --upgrade --no-cache less=685-r0 && \
    apk add --upgrade --no-cache vim=9.2.0567-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
ENV TZ=Australia/Perth
ENV LANG=en_AU.UTF-8
ENV LANGUAGE=en_AU.UTF-8

FROM image_base AS image_build

FROM image_build AS image_runtime
COPY target/package/main/resources/image/. /asystem/etc
WORKDIR /asystem/etc
