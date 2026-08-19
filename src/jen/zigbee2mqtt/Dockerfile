# NOTES: https://github.com/Koenkk/zigbee2mqtt/releases
FROM koenkk/zigbee2mqtt:2.13.0 AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=5.3.9-r1 && \
    apk add --upgrade --no-cache coreutils=9.11-r0 && \
    apk add --upgrade --no-cache less=702-r0 && \
    apk add --upgrade --no-cache curl=8.21.0-r0 && \
    apk add --upgrade --no-cache vim=9.2.0854-r0 && \
    apk add --upgrade --no-cache jq=1.8.1-r0 && \
    apk add --upgrade --no-cache mosquitto-clients=2.1.2-r1 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
COPY target/package/main/resources/image/. /asystem/etc

FROM image_base AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["docker-entrypoint.sh"]
CMD [ "/sbin/tini", "--", "node", "/app/index.js"]
