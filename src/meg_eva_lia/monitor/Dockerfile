ARG ASYSTEM_TELEGRAF_VERSION="latest"

FROM telegraf:${ASYSTEM_TELEGRAF_VERSION} AS image_upstream

FROM image_upstream AS image_base
USER root
RUN apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install mosquitto-clients=2.0.11-1.2+deb12u1 && \
    apt-get clean

FROM image_base AS image_build

FROM image_build AS image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
