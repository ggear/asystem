# https://github.com/weewx/weewx/releases
FROM python:3.8.5-slim-buster as image_base

ENV WEEWX_VERSION="4.6.2"
ENV WEEWX_HOME="/home/weewx"
ENV WEEWX_ARCHIVE="weewx-${WEEWX_VERSION}.tar.gz"

FROM image_base as image_package
RUN apt-get update && apt-get -y --no-install-recommends install \
  build-essential=12.6 \
  lbzip2=2.5-2 \
  libjpeg-dev=1:1.5.2-2+deb10u1 \
  zlib1g=1:1.2.11.dfsg-1 \
  zlib1g-dev=1:1.2.11.dfsg-1 \
  tar=1.30+dfsg-6 \
  wget=1.20.1-1.1 \
  rsyslog=8.1901.0-1+deb10u1 \
  gnupg2=2.2.12-1+deb10u1 \
  apache2=2.4.38-3+deb10u7 \
  default-mysql-client=1.0.5 \
  apache2-utils=2.4.38-3+deb10u7 \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
WORKDIR /tmp
RUN wget https://downloads.python.org/pypy/pypy3.8-v7.3.7-linux64.tar.bz2
RUN tar xf pypy3.8-v7.3.7-linux64.tar.bz2
RUN mv pypy3.8-v7.3.7-linux64 /var/lib/pypy
RUN /var/lib/pypy/bin/pypy -m ensurepip --default-pip
RUN /var/lib/pypy/bin/pypy -mpip install -U pip wheel
ENV PIP_PACKAGES="configobj==5.0.6 \
                  requests==2.27.1 \
                  cheetah3==3.2.6.post1 \
                  pillow==9.0.1 \
                  pyserial==3.5 \
                  pyusb==1.2.1 \
                  ephem==4.1.3 \
                  paho-mqtt==1.6.1 \
                  pyephem==9.99 \
                  pymysql==1.0.2"
RUN pip install --no-cache ${PIP_PACKAGES}
RUN /var/lib/pypy/bin/pip install --no-cache ${PIP_PACKAGES}

FROM image_package as image_install
WORKDIR /tmp
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf
RUN mkdir -p /data/html && touch /data/html/index.html
RUN rm -rf /var/www/html && ln -s /data/html /var/www/html
COPY src/main/resources/apache2.conf /etc/apache2
RUN mkdir -p ${WEEWX_HOME}
RUN wget -q -O "${WEEWX_ARCHIVE}" "http://www.weewx.com/downloads/released_versions/${WEEWX_ARCHIVE}"
RUN tar --extract --gunzip --directory ${WEEWX_HOME} --strip-components=1 --file "${WEEWX_ARCHIVE}"
RUN wget -O weewx-mqtt.zip https://github.com/matthewwall/weewx-mqtt/archive/master.zip
RUN /home/weewx/bin/wee_extension --install weewx-mqtt.zip

FROM image_install as image_runtime
WORKDIR ${WEEWX_HOME}
RUN python ./setup.py build
RUN python ./setup.py install
RUN /var/lib/pypy/bin/pypy ./setup.py build
RUN /var/lib/pypy/bin/pypy ./setup.py install

RUN rm -rf /home/weewx/weewx.conf*
COPY target/package/main/resources/config/weewx.conf /home/weewx
# RUN /home/weewx/bin/wee_device --set-interval=5

COPY src/main/resources/entrypoint.sh ./

EXPOSE 80
VOLUME ["/data"]

ENTRYPOINT ["./entrypoint.sh"]
CMD ["/data/weewx.conf"]
