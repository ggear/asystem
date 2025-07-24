# Notes: https://docs.influxdata.com/influxdb3/core/release-notes
FROM quay.io/influxdb/influxdb3-enterprise:latest AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b7 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u12 && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1 && \
    apt-get -y --no-install-recommends --allow-downgrades install netcat-openbsd=1.219-1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build

FROM image_base AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["/usr/bin/entrypoint.sh"]
CMD ["serve"]
