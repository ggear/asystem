FROM quay.io/influxdb/influxdb:v2.0.6 as image_base

USER root
RUN apt-get install -y \
  netcat=1.10-41.1 \
  jq=1.5+dfsg-2+b1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["influxd"]
