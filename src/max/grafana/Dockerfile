# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_GRAFANA_VERSION="latest"
FROM grafana/grafana:${ASYSTEM_GRAFANA_VERSION} AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=5.3.9-r1 && \
    apk add --upgrade --no-cache coreutils=9.11-r0 && \
    apk add --upgrade --no-cache less=702-r0 && \
    apk add --upgrade --no-cache curl=8.22.0-r0 && \
    apk add --upgrade --no-cache vim=9.2.1091-r0 && \
    apk add --upgrade --no-cache jq=1.8.2-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_GCX_VERSION
ARG TARGETARCH
RUN cd /tmp && \
    curl -sfSLO "https://github.com/grafana/gcx/releases/download/v${ASYSTEM_GCX_VERSION}/gcx_${ASYSTEM_GCX_VERSION}_linux_${TARGETARCH}.tar.gz" && \
    curl -sfSLO "https://github.com/grafana/gcx/releases/download/v${ASYSTEM_GCX_VERSION}/gcx_${ASYSTEM_GCX_VERSION}_checksums.txt" && \
    grep "gcx_${ASYSTEM_GCX_VERSION}_linux_${TARGETARCH}.tar.gz" "gcx_${ASYSTEM_GCX_VERSION}_checksums.txt" | sha256sum -c - && \
    tar -xzf "gcx_${ASYSTEM_GCX_VERSION}_linux_${TARGETARCH}.tar.gz" -C /usr/local/bin gcx && \
    rm -f gcx_* && \
    gcx --version

FROM image_base AS image_build
COPY target/package/main/resources/image/. /asystem/etc

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT [ "/run.sh" ]
