# https://github.com/Koenkk/zigbee2mqtt/releases
FROM koenkk/zigbee2mqtt:1.41.0 AS image_upstream

FROM image_upstream AS image_base
USER root
RUN apk update && \
    apk add --no-cache bash=5.2.15-r5 && \
    apk add --no-cache vim=9.0.2073-r0 && \
    apk add --no-cache python3=3.11.10-r1 && \
    apk add --no-cache mosquitto-clients=2.0.18-r0 && \
    apk cache clean

FROM image_base AS image_build
COPY src/.py_deps.txt /asystem/
RUN (python3 -m ensurepip 2> /dev/null || true) && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade -r /asystem/.py_deps.txt && \
    pip3 cache purge

FROM image_build AS image_runtime
ENTRYPOINT ["docker-entrypoint.sh"]
CMD [ "/sbin/tini", "--", "node", "index.js"]
