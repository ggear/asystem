# https://mariadb.org/mariadb/all-releases
FROM mariadb:11.0.2 as image_base

FROM image_base as image_package

FROM image_package as image_install

FROM image_install as image_runtime
RUN echo "USE mysql;" > /docker-entrypoint-initdb.d/timezones.sql &&  mysql_tzinfo_to_sql /usr/share/zoneinfo >> /docker-entrypoint-initdb.d/timezones.sql

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mariadbd"]
