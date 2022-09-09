# https://github.com/vernemq/vernemq/releases
FROM vernemq/vernemq:1.12.3-alpine as image_base

FROM image_base as image_package
USER root
RUN apk add --no-cache \
  mosquitto-clients==1.6.12-r3

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT [ "start_vernemq" ]
