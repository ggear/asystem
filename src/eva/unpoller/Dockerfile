FROM debian:12.8-slim AS image_upstream

ARG ASYSTEM_UNPOLLER_VERSION

FROM image_upstream AS image_base

FROM image_base AS image_build
RUN \
    cd /tmp && \
    curl -sfSL -o "unpoller.tar.gz" "https://github.com/unpoller/unpoller/releases/download/v${ASYSTEM_UNPOLLER_VERSION}/unpoller_${ASYSTEM_UNPOLLER_VERSION}_linux_amd64.tar.gz" && \
    tar xvzf "unpoller.tar.gz" && \
    cp "unpoller" "/usr/local/bin" && \
    chmod a+x "/usr/local/bin/unpoller" && \
    unpoller --version

FROM image_build AS image_runtime
