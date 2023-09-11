# https://github.com/influxdata/telegraf/releases
FROM telegraf:1.27.4 as image_base

FROM image_base as image_package
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install mosquitto-clients=2.0.11-1.2
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_install

FROM image_install as image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime


ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
