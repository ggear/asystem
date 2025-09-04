ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION="slim"

FROM debian:${ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION} AS image_upstream

FROM image_upstream AS image_base
USER root
RUN \
    dpkg --add-architecture amd64 && \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install qemu-user-static && \
    apt-get -y --no-install-recommends --allow-downgrades install libc6:amd64 && \
    apt-get -y --no-install-recommends --allow-downgrades install libstdc++6:amd64 && \
    apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b8 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u12 && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1 && \
    apt-get -y --no-install-recommends --allow-downgrades install unzip=6.0-28 && \
    apt-get -y --no-install-recommends --allow-downgrades install ffmpeg=7:5.1.7-0+deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install sqlite3=3.40.1-2+deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install ca-certificates=20230311+deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install libmediainfo0v5=23.04+dfsg-1 && \
    apt-get -y --no-install-recommends --allow-downgrades install libchromaprint-tools=1.5.1-2+b1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build
RUN \
    tar -xvzf /asystem/etc/*.gz -C /opt && \
    chmod +x /opt/Sonarr/Sonarr && \
    rm /asystem/etc/*.gz

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["/opt/Sonarr/Sonarr", "--nobrowser"]
