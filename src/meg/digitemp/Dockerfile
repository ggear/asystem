# https://github.com/influxdata/telegraf/releases
FROM telegraf:1.25.3 as image_base

FROM image_base as image_package
ARG PYTHON_VERSION
ENV PYTHONUNBUFFERED=1
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install python3=$PYTHON_VERSION-3
RUN apt-get -y --no-install-recommends install python3-dev=$PYTHON_VERSION-3
RUN apt-get -y --no-install-recommends install python-is-python3=$PYTHON_VERSION-1
RUN apt-get -y --no-install-recommends install python3-pip=20.3.4-4+deb11u1
RUN apt-get -y --no-install-recommends install mosquitto-clients=2.0.11-1
RUN apt-get -y --no-install-recommends install jq=1.6-2.1
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_install

FROM image_install as image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 pip install && rm -rf /asystem/reqs_run.txt
COPY src/main/python/ /asystem/

HEALTHCHECK --interval=311s --start-period=60s --start-interval=20s --timeout=20s --retries=3 CMD /bootstrap/healthcheck.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
