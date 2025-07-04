# Notes: https://github.com/Koenkk/zigbee2mqtt/releases
FROM koenkk/zigbee2mqtt:2.3.0 AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apk update && \
    apk add --upgrade --no-cache bash=5.2.37-r0 && \
    apk add --upgrade --no-cache less=668-r0 && \
    apk add --upgrade --no-cache curl=8.12.1-r1 && \
    apk add --upgrade --no-cache vim=9.1.1105-r0 && \
    apk add --upgrade --no-cache jq=1.7.1-r0 && \
    apk add --upgrade --no-cache py3-pip=24.3.1-r0 && \
    apk add --upgrade --no-cache python3=3.12.10-r0 && \
    apk add --upgrade --no-cache mosquitto-clients=2.0.20-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY src/main/python /asystem/bin/python
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build
COPY src/main/python/.py_deps.txt /asystem/
RUN (python3 -m ensurepip 2> /dev/null || true) && \
    pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir --upgrade -r /asystem/bin/python/.py_deps.txt && \
    pip3 cache purge

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["docker-entrypoint.sh"]
CMD [ "/sbin/tini", "--", "node", "index.js"]
