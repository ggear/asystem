# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION="slim"
FROM debian:${ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION} AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b13 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install coreutils=9.1-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install unzip=6.0-28 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install ffmpeg=7:5.1.9-0+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install sqlite3=3.40.1-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install ca-certificates=20230311+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libmediainfo0v5=23.04+dfsg-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libchromaprint-tools=1.5.1-2+b1 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
ARG ASYSTEM_SONARR_VERSION
ARG TARGETARCH
COPY target/package/main/resources/image/. /asystem/etc
RUN case "${TARGETARCH}" in \
      amd64) SONARR_ARCH="x64" ;; \
      arm64) SONARR_ARCH="arm64" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    curl -fL "https://github.com/Sonarr/Sonarr/releases/download/v${ASYSTEM_SONARR_VERSION}/Sonarr.main.${ASYSTEM_SONARR_VERSION}.linux-${SONARR_ARCH}.tar.gz" \
      | tar -xz -C /opt && \
    chmod +x /opt/Sonarr/Sonarr

FROM image_base AS image_build

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["/opt/Sonarr/Sonarr", "--nobrowser"]
