# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION="slim"
FROM debian:${ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION} AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b10 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install coreutils=9.1-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install mosquitto-clients=2.0.11-1.2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
COPY target/go/bin/supervisor /asystem/bin
RUN chmod +x /asystem/bin/supervisor

FROM image_base AS image_build
COPY target/package/main/resources/image/. /asystem/etc

FROM image_build AS image_runtime
WORKDIR /asystem/etc
CMD ["sleep", "9999"]
