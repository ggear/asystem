# NOTES: https://www.postgresql.org/docs/release
FROM postgres:17.5-bullseye AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.1-2+deb11u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
RUN localedef -i en_AU -c -f UTF-8 -A /usr/share/locale/locale.alias en_AU.UTF-8
ENV TZ=Australia/Perth
ENV LANG=en_AU.UTF-8
ENV LANGUAGE=en_AU.UTF-8
ENV LC_ALL=en_AU.UTF-8

FROM image_base AS image_build

FROM image_build AS image_runtime
COPY target/package/main/resources/image/. /asystem/etc
WORKDIR /asystem/etc
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
