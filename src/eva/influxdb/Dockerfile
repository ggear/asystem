# https://github.com/influxdata/influxdb/releases
FROM influxdb:2.7.7-alpine as image_base

FROM image_base as image_package
USER root
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apk add --no-cache jq==1.6-r4
RUN apk add --no-cache curl==8.5.0-r0
RUN apk add --no-cache netcat-openbsd==1.219-r1

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
