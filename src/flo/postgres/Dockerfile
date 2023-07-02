# https://www.postgresql.org/docs/release
FROM postgres:15.3-bookworm as image_base

FROM image_base as image_package
RUN localedef -i en_AU -c -f UTF-8 -A /usr/share/locale/locale.alias en_AU.UTF-8
ENV LANG en_AU.utf8

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
