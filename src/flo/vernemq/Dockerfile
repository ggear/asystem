# https://github.com/vernemq/vernemq/releases
FROM vernemq/vernemq:1.13.0-alpine as image_base

FROM image_base as image_package
USER root
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apk add --no-cache mosquitto-clients==2.0.15-r3

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT [ "start_vernemq" ]
