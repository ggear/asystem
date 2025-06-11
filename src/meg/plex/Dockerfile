# https://www.videohelp.com/software/Plex/version-history
FROM linuxserver/plex:1.41.8 AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.21-2ubuntu4 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2ubuntu2.1 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=8.5.0-2ubuntu10.6 && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.1.0016-1ubuntu7.8 && \
    apt-get -y --no-install-recommends --allow-downgrades install xq=1.0.0-2ubuntu0.24.04.2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build

FROM image_build AS image_runtime
