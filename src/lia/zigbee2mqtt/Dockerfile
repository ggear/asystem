# https://github.com/Koenkk/zigbee2mqtt/releases
FROM koenkk/zigbee2mqtt:1.32.0 as image_base

FROM image_base as image_package
USER root
# TODO: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apk add --no-cache mosquitto-clients==2.0.15-r3

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD [ "/sbin/tini", "--", "node", "index.js"]
