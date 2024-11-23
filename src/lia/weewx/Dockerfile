# https://github.com/weewx/weewx/releases
FROM python:3.12.5-bookworm AS image_base

ARG ASYSTEM_WEEWX_VERSION

ENV WEEWX_HOME="/home/weewx"
ENV PYTHONDONTWRITEBYTECODE=1

FROM image_base AS image_package
USER root
RUN apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install tar=1.34+dfsg-1.2+deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install gnupg2=2.2.40-1.1 && \
    apt-get -y --no-install-recommends --allow-downgrades install apache2=2.4.62-1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install apache2-utils=2.4.62-1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install mosquitto-clients=2.0.11-1.2+deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install default-mysql-client=1.1.0 && \
    apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    apt-get -y --no-install-recommends --allow-downgrades install lbzip2=2.5-2.3 && \
    apt-get -y --no-install-recommends --allow-downgrades install libjpeg-dev=1:2.1.5-2 && \
    apt-get -y --no-install-recommends --allow-downgrades install zlib1g-dev=1:1.2.13.dfsg-1 && \
    apt-get clean

FROM image_package AS image_install
WORKDIR /tmp
RUN mkdir -p /data/html && touch /data/html/index.html && \
    rm -rf /var/www/html && ln -s /data/html /var/www/html
COPY src/main/resources/apache2.conf /etc/apache2


# TODO: Convert to py_deps, check pull doesnt ask to update to 0a2 release
ENV PIP_PACKAGES="\
  poetry==1.8.2 \
  paho-mqtt==1.6.1 \
"
RUN pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip
RUN pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir ${PIP_PACKAGES}

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
RUN poetry build -vv
RUN poetry install -vv
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

FROM image_install AS image_runtime
WORKDIR ${WEEWX_HOME}
COPY src/main/resources/entrypoint.sh /
EXPOSE 80
VOLUME ["/data"]
ENTRYPOINT ["/entrypoint.sh"]
