# https://github.com/grafana/grafana/releases
FROM grafana/grafana:11.4.0 AS image_upstream

ARG ASYSTEM_GRIZZLY_VERSION

FROM image_upstream AS image_base
USER root
RUN \
    apk update && \
    apk add --no-cache bash=5.2.26-r0 && \
    apk add --no-cache less=643-r2 && \
    apk add --no-cache vim=9.1.0707-r0 && \
    apk add --no-cache jq=1.7.1-r0 && \
    apk cache clean && rm -rf /var/cache/apk/* && \
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
