# https://github.com/vernemq/vernemq/releases
FROM vernemq/vernemq:2.0.1-alpine AS image_upstream

FROM image_upstream AS image_base
USER root
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apk add --no-cache mosquitto-clients==2.0.18-r0

FROM image_base AS image_build

FROM image_build AS image_runtime

ENTRYPOINT [ "start_vernemq" ]
