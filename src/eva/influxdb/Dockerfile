# https://github.com/influxdata/influxdb/releases
FROM influxdb:2.7.10-alpine AS image_base

FROM image_base AS image_package
USER root
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apk add --no-cache jq==1.7.1-r0
RUN apk add --no-cache curl==8.10.1-r0
RUN apk add --no-cache netcat-openbsd==1.226-r0

FROM image_package AS image_install

FROM image_install AS image_runtime

ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
