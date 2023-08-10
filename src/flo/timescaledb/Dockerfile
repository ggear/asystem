# https://github.com/timescale/timescaledb/releases
FROM timescale/timescaledb:2.11.1-pg15 as image_base

FROM image_base as image_package
RUN localedef -i en_AU -c -f UTF-8 -A /usr/share/locale/locale.alias en_AU.UTF-8
ENV LANG en_AU.utf8

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
