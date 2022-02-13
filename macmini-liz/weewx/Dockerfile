FROM python:3.8.5-slim-buster as image_base

FROM image_base as image_package
ENV WEEWX_VERSION="4.6.2"
ENV WEEWX_HOME="/home/weewx"
ENV WEEWX_ARCHIVE="weewx-${WEEWX_VERSION}.tar.gz"
RUN apt-get update && apt-get -y --no-install-recommends install \
  tar=1.30+dfsg-6 \
  wget=1.20.1-1.1 \
  rsyslog=8.1901.0-1 \
  gnupg2=2.2.12-1+deb10u1 \
  apache2=2.4.38-3+deb10u7 \
  default-mysql-client=1.0.5 \
  apache2-utils=2.4.38-3+deb10u7 \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN pip install --no-cache \
  configobj==5.0.6 \
  requests==2.24.0 \
  cheetah3==3.2.5 \
  pillow==7.2.0 \
  pyserial==3.4 \
  pyusb==1.0.2 \
  ephem==3.7.7.0 \
  paho-mqtt==1.6.1 \
  pymysql==1.0.2

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

RUN rm -rf /home/weewx/weewx.conf*
COPY target/package/main/resources/config/weewx.conf /home/weewx
# RUN /home/weewx/bin/wee_device --set-interval=5

COPY src/main/resources/entrypoint.sh ./

EXPOSE 80
VOLUME ["/data"]

ENTRYPOINT ["./entrypoint.sh"]
CMD ["/data/weewx.conf"]
