# NOTES: https://mariadb.org/mariadb/all-releases
FROM mariadb:12.0.2 AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.21-2ubuntu4 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install coreutils=9.4-3ubuntu6.1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install less=590-2ubuntu2.1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.1.0016-1ubuntu7.9 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base

FROM image_base AS image_build

FROM image_build AS image_runtime
COPY target/package/main/resources/image/. /asystem/etc
WORKDIR /asystem/etc
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mariadbd"]
