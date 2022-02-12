FROM mariadb:10.7.1 as image_base

FROM image_base as image_package

FROM image_package as image_install

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mariadbd"]
