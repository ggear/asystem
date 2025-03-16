ARG ASYSTEM_TELEGRAF_VERSION="latest"

FROM telegraf:${ASYSTEM_TELEGRAF_VERSION} AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b7 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install mosquitto-clients=2.0.11-1.2+deb12u1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build
RUN \
    cp /asystem/etc/telegraf.conf /etc/telegraf/telegraf.conf

FROM image_build AS image_runtime
ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
