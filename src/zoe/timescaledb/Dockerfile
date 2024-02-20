# https://github.com/timescale/timescaledb/releases
FROM timescale/timescaledb:2.14.1-pg15 as image_base

FROM image_base as image_package
RUN apk update
RUN apk add --no-cache tzdata
RUN cp /usr/share/zoneinfo/Australia/Perth /etc/localtime
RUN echo "Australia/Perth" >  /etc/timezone
ENV TZ Australia/Perth
ENV LANG en_AU.UTF-8
ENV LANGUAGE en_AU.UTF-8
ENV LC_ALL en_AU.UTF-8

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
