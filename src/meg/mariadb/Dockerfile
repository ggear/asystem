# https://mariadb.org/mariadb/all-releases
FROM mariadb:11.5.2 AS image_upstream

FROM image_upstream AS image_base

FROM image_base AS image_build

FROM image_build AS image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mariadbd"]
