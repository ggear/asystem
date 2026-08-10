# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION="slim"
FROM debian:${ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION} AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b9 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install procps=2:4.0.2-3 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install coreutils=9.1-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install ca-certificates=20230311+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_UNPOLLER_VERSION
COPY target/package/main/resources/image/. /asystem/etc
RUN cd /tmp && \
    curl -sfSL -o "unpoller.tar.gz" "https://github.com/unpoller/unpoller/releases/download/v${ASYSTEM_UNPOLLER_VERSION}/unpoller_${ASYSTEM_UNPOLLER_VERSION}_linux_amd64.tar.gz" && \
    tar xvzf "unpoller.tar.gz" && \
    cp "unpoller" "/usr/local/bin" && \
    chmod a+x "/usr/local/bin/unpoller" && \
    mkdir -p "/etc/unifi-poller" && \
    cp /asystem/etc/up.conf /etc/unifi-poller/up.conf && \
    mkdir -p "/usr/local/lib/unpoller/web" && \
    cd / &&  \
    rm -rf /tmp/* && \
    unpoller --version

FROM image_base AS image_build

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT [ "/usr/local/bin/unpoller" ]