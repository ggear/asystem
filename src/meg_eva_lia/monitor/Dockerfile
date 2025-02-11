ARG ASYSTEM_TELEGRAF_VERSION="latest"

FROM telegraf:${ASYSTEM_TELEGRAF_VERSION} AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u8 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build

FROM image_build AS image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
