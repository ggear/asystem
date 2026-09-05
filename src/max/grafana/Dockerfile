# NOTES: https://github.com/grafana/grafana/releases
FROM grafana/grafana:13.2.1 AS image_upstream
USER root
RUN apk update && \
    apk add --upgrade --no-cache bash=5.3.9-r1 && \
    apk add --upgrade --no-cache coreutils=9.11-r0 && \
    apk add --upgrade --no-cache less=702-r0 && \
    apk add --upgrade --no-cache curl=8.22.0-r0 && \
    apk add --upgrade --no-cache vim=9.2.1014-r0 && \
    apk add --upgrade --no-cache jq=1.8.2-r0 && \
    (apk cache clean || true) && rm -rf /var/cache/apk/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_GRIZZLY_VERSION
RUN \
    curl -sfSL -o "/usr/local/bin/grr" "https://github.com/grafana/grizzly/releases/download/${ASYSTEM_GRIZZLY_VERSION}/grr-linux-amd64" && \
    chmod a+x "/usr/local/bin/grr" && \
    mkdir -p /root/.config/grizzly && \
    grr --version

FROM image_base AS image_build
COPY target/package/main/resources/image/. /asystem/etc
RUN cp -f /asystem/etc/config/grafana.ini /etc/grafana

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT [ "/run.sh" ]
