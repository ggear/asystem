# https://mariadb.org/mariadb/all-releases
FROM mariadb:11.1.2 as image_base

FROM image_base as image_package

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mariadbd"]
