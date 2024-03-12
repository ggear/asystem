# https://github.com/weewx/weewx/releases
FROM python:3.12.2-slim-bookworm as image_base

ENV WEEWX_HOME="/home/weewx"
ENV PYTHONDONTWRITEBYTECODE=1

FROM image_base as image_package
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install build-essential=12.9
RUN apt-get -y --no-install-recommends install lbzip2=2.5-2.3
RUN apt-get -y --no-install-recommends install libjpeg-dev=1:2.1.5-2
RUN apt-get -y --no-install-recommends install zlib1g-dev=1:1.2.13.dfsg-1
RUN apt-get -y --no-install-recommends install tar=1.34+dfsg-1.2+deb12u1
RUN apt-get -y --no-install-recommends install gnupg2=2.2.40-1.1
RUN apt-get -y --no-install-recommends install default-mysql-client=1.1.0
RUN apt-get -y --no-install-recommends install apache2=2.4.57-2
RUN apt-get -y --no-install-recommends install apache2-utils=2.4.57-2
RUN apt-get -y --no-install-recommends install mosquitto-clients=2.0.11-1.2+deb12u1
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_install
WORKDIR /tmp
RUN mkdir -p /data/html && touch /data/html/index.html
RUN rm -rf /var/www/html && ln -s /data/html /var/www/html
COPY src/main/resources/apache2.conf /etc/apache2
ENV PIP_PACKAGES="\
  poetry==1.8.2 \
  paho-mqtt==1.6.1 \
"
RUN pip install --default-timeout=1000 --no-cache-dir ${PIP_PACKAGES}

#INFO: Disable pypy
#WORKDIR /tmp
#RUN wget https://downloads.python.org/pypy/pypy3.8-v7.3.7-linux64.tar.bz2
#RUN tar xf pypy3.8-v7.3.7-linux64.tar.bz2
#RUN mv pypy3.8-v7.3.7-linux64 /var/lib/pypy
#RUN /var/lib/pypy/bin/pypy -m ensurepip --default-pip
#RUN /var/lib/pypy/bin/pypy -mpip install -U pip wheel
#RUN /var/lib/pypy/bin/pip install --no-cache ${PIP_PACKAGES}

WORKDIR /tmp
COPY src/build/resources/weewx-*.tar.gz /tmp
RUN mkdir -p /tmp/weewx
RUN tar --extract --gunzip --directory /tmp/weewx --strip-components=1 --file weewx-*.tar.gz
WORKDIR /tmp/weewx
RUN poetry build
RUN poetry install
WORKDIR /tmp/weewx/dist
RUN pip install weewx-*.whl
RUN rm -rf ${WEEWX_HOME}
RUN mkdir -p $(dirname ${WEEWX_HOME})
RUN ln -s $(pip show weewx | grep Location | sed 's/Location: //')/weewx_data ${WEEWX_HOME}
RUN mkdir -p /etc/weewx
RUN rm -rf /etc/weewx/weewx.conf*
COPY target/package/main/resources/config/weewx.conf /etc/weewx
COPY src/build/resources/weewx-mqtt.zip /tmp
RUN weectl extension install -y /tmp/weewx-mqtt.zip
RUN rm -rf /tmp/* /etc/weewx/weewx.conf*

FROM image_install as image_runtime
WORKDIR ${WEEWX_HOME}

COPY src/main/resources/entrypoint.sh /

EXPOSE 80
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
