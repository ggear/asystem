# https://mariadb.org/mariadb/all-releases
FROM mariadb:11.5.2 AS image_base

FROM image_base AS image_package

FROM image_package AS image_install

FROM image_install AS image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mariadbd"]
