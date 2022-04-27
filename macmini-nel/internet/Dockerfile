FROM telegraf:1.22.2 as image_base

FROM image_base as image_package
ARG PYTHON_VERSION
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get -y --no-install-recommends install \
  python3=$PYTHON_VERSION-3 \
  python3-dev=$PYTHON_VERSION-3 \
  python-is-python3=$PYTHON_VERSION-1 \
  python3-pip=20.3.4-4+deb11u1 \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_install

FROM image_install as image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 pip install && rm -rf /asystem/reqs_run.txt
COPY src/main/resources/mqtt_metadata.csv /asystem
COPY src/main/python/internet/internet.py /asystem

ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
