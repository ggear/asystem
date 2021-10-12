FROM quay.io/influxdb/influxdb:v2.0.9 as image_base

FROM image_base as image_package
USER root
RUN apt-get install -y \
  netcat=1.10-41.1 \
  jq=1.5+dfsg-2+b1 \
  curl=7.64.0-4+deb10u2

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
