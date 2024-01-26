# https://github.com/weewx/weewx/releases
FROM python:3.11.5-slim-bullseye as image_base

ENV WEEWX_HOME="/home/weewx"

FROM image_base as image_package
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install build-essential=12.9
RUN apt-get -y --no-install-recommends install lbzip2=2.5-2.1
RUN apt-get -y --no-install-recommends install libjpeg-dev=1:2.0.6-4
RUN apt-get -y --no-install-recommends install zlib1g-dev=1:1.2.11.dfsg-2+deb11u2
RUN apt-get -y --no-install-recommends install tar=1.34+dfsg-1
RUN apt-get -y --no-install-recommends install wget=1.21-1+deb11u1
RUN apt-get -y --no-install-recommends install rsyslog=8.2102.0-2+deb11u1
RUN apt-get -y --no-install-recommends install gnupg2=2.2.27-2+deb11u2
RUN apt-get -y --no-install-recommends install default-mysql-client=1.0.7
RUN apt-get -y --no-install-recommends install apache2=2.4.56-1~deb11u2
RUN apt-get -y --no-install-recommends install apache2-utils=2.4.56-1~deb11u2
RUN apt-get -y --no-install-recommends install mosquitto-clients=2.0.11-1
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

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
RUN pip install --default-timeout=1000 --no-cache ${PIP_PACKAGES}

# Disable pypy
#WORKDIR /tmp
#RUN wget https://downloads.python.org/pypy/pypy3.8-v7.3.7-linux64.tar.bz2
#RUN tar xf pypy3.8-v7.3.7-linux64.tar.bz2
#RUN mv pypy3.8-v7.3.7-linux64 /var/lib/pypy
#RUN /var/lib/pypy/bin/pypy -m ensurepip --default-pip
#RUN /var/lib/pypy/bin/pypy -mpip install -U pip wheel
#RUN /var/lib/pypy/bin/pip install --no-cache ${PIP_PACKAGES}

FROM image_package as image_install
WORKDIR /tmp
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf
RUN mkdir -p /data/html && touch /data/html/index.html
RUN rm -rf /var/www/html && ln -s /data/html /var/www/html
COPY src/main/resources/apache2.conf /etc/apache2
RUN mkdir -p ${WEEWX_HOME}
COPY src/build/resources/weewx-*.tar.gz /tmp
RUN tar --extract --gunzip --directory ${WEEWX_HOME} --strip-components=1 --file weewx-*.tar.gz
RUN wget -O weewx-mqtt.zip https://github.com/matthewwall/weewx-mqtt/archive/master.zip
RUN /home/weewx/bin/wee_extension --install weewx-mqtt.zip

FROM image_install as image_runtime
WORKDIR ${WEEWX_HOME}
RUN python ./setup.py build
RUN python ./setup.py install

# Disable pypy
#RUN /var/lib/pypy/bin/pypy ./setup.py build
#RUN /var/lib/pypy/bin/pypy ./setup.py install

RUN rm -rf /home/weewx/weewx.conf*
COPY target/package/main/resources/config/weewx.conf /home/weewx
# RUN /home/weewx/bin/wee_device --set-interval=5

COPY src/main/resources/entrypoint.sh ./

EXPOSE 80
VOLUME ["/data"]

ENTRYPOINT ["./entrypoint.sh"]
CMD ["/data/weewx.conf"]
