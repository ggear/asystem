# Notes: https://github.com/grafana/grafana/releases
FROM grafana/grafana:12.1.1 AS image_upstream

# Defined: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_GRIZZLY_VERSION

FROM image_upstream AS image_base
USER root
RUN \
    apk update && \
    apk add --upgrade --no-cache bash=5.2.37-r0 && \
    apk add --upgrade --no-cache less=679-r0 && \
    apk add --upgrade --no-cache curl=8.14.1-r1 && \
    apk add --upgrade --no-cache vim=9.1.1566-r0 && \
    apk add --upgrade --no-cache jq=1.8.0-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build
RUN \
    curl -sfSL -o "/usr/local/bin/grr" "https://github.com/grafana/grizzly/releases/download/${ASYSTEM_GRIZZLY_VERSION}/grr-linux-amd64" && \
    chmod a+x "/usr/local/bin/grr" && \
    mkdir -p /root/.config/grizzly && \
    grr --version

FROM image_build AS image_runtime
RUN \
   cp -f /asystem/etc/config/grafana.ini /etc/grafana
ENTRYPOINT [ "/run.sh" ]
