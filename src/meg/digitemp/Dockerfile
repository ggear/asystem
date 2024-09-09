# https://github.com/influxdata/telegraf/releases
FROM telegraf:1.28.1 AS image_base

FROM image_base AS image_package
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install build-essential=12.9
RUN apt-get -y --no-install-recommends install libbz2-dev=1.0.8-5+b1
RUN apt-get -y --no-install-recommends install libffi-dev=3.4.4-1
RUN apt-get -y --no-install-recommends install zlib1g-dev=1:1.2.13.dfsg-1
RUN apt-get -y --no-install-recommends install libssl-dev=3.0.11-1~deb12u2
RUN apt-get -y --no-install-recommends install jq=1.6-2.1
RUN apt-get -y --no-install-recommends install mosquitto-clients=2.0.11-1.2+deb12u1
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package AS image_install
ARG PYTHON_VERSION
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN mkdir -p /tmp
WORKDIR /tmp
RUN wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz
RUN tar zxf Python-$PYTHON_VERSION.tgz
WORKDIR /tmp/Python-$PYTHON_VERSION
RUN ./configure --prefix=/usr/local
RUN make
RUN make install
RUN /usr/local/bin/python3 --version
RUN /usr/local/bin/python3 -m pip install --default-timeout=1000 --upgrade pip
RUN /usr/local/bin/pip3 --version
RUN rm -rf /tmp/*

FROM image_install AS image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/.py_prod.txt /asystem
RUN cat /asystem/.py_prod.txt | xargs -n 1 /usr/local/bin/pip3 install --default-timeout=1000 && rm -rf /asystem/reqs_run.txt
COPY src/main/python/ /asystem/

# TODO: Requires Docker 25.0.0+
#HEALTHCHECK --interval=311s --start-period=60s --start-interval=20s --timeout=20s --retries=3 CMD /bootstrap/healthcheck.sh
HEALTHCHECK --interval=311s --start-period=60s --timeout=20s --retries=3 CMD /bootstrap/healthcheck.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
