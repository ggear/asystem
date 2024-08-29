# https://github.com/influxdata/telegraf/releases
FROM telegraf:1.28.1 AS image_base

FROM image_base AS image_package
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install mosquitto-clients=2.0.11-1.2+deb12u1
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package AS image_install

FROM image_install AS image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime


ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
