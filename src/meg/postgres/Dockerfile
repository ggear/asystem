# https://www.postgresql.org/docs/release
FROM postgres:14.13-bullseye AS image_upstream

FROM image_upstream AS image_base
RUN localedef -i en_AU -c -f UTF-8 -A /usr/share/locale/locale.alias en_AU.UTF-8
ENV TZ=Australia/Perth
ENV LANG=en_AU.UTF-8
ENV LANGUAGE=en_AU.UTF-8
ENV LC_ALL=en_AU.UTF-8

FROM image_base AS image_build

FROM image_build AS image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
