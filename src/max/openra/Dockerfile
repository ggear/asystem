# NOTES: https://github.com/OpenRA/OpenRA/releases
FROM ghcr.io/dkruyt/openra:20250330 AS image_upstream

FROM image_upstream AS image_base
USER root

FROM image_base AS image_build
COPY target/package/main/resources/image/. /asystem/etc

FROM image_build AS image_runtime
WORKDIR /asystem/etc
CMD ["/home/openra/lib/openra/launch-dedicated.sh"]
