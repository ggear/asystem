# https://github.com/Koenkk/zigbee2mqtt/releases
FROM koenkk/zigbee2mqtt:1.26.2 as image_base

FROM image_base as image_package
USER root
RUN apk add --no-cache \
  mosquitto-clients==2.0.14-r0

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD [ "/sbin/tini", "--", "node", "index.js"]
