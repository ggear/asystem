# https://github.com/timescale/timescaledb/releases
FROM timescale/timescaledb:2.17.2-pg15 AS image_upstream

FROM image_upstream AS image_base
RUN apk update
RUN apk add --no-cache tzdata
RUN cp /usr/share/zoneinfo/Australia/Perth /etc/localtime
RUN echo "Australia/Perth" >  /etc/timezone
ENV TZ=Australia/Perth
ENV LANG=en_AU.UTF-8
ENV LANGUAGE=en_AU.UTF-8
ENV LC_ALL=en_AU.UTF-8

FROM image_base AS image_build

FROM image_build AS image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
