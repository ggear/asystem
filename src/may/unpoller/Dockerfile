ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION="slim"

FROM debian:${ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION} AS image_upstream

# Defined: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_UNPOLLER_VERSION

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b7 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u12 && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1 && \
    apt-get -y --no-install-recommends --allow-downgrades install ca-certificates=20230311 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build
RUN \
    cd /tmp && \
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

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT [ "/usr/local/bin/unpoller" ]