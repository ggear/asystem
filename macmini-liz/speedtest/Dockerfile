FROM python:3.8.5-slim-buster as image_base

ENV WEEWX_VERSION="4.1.1"
ENV WEEWX_HOME="/home/weewx"
ENV WEEWX_ARCHIVE="weewx-${WEEWX_VERSION}.tar.gz"

RUN apt-get update && apt-get -y --no-install-recommends install \
  rsyslog=8.1901.0-1 \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip install --no-cache \
  configobj==5.0.6

WORKDIR /tmp
#COPY src/main/python/weewx/weewx_anode_plugin.py /home/weewx/bin/user
#COPY src/main/resources/entrypoint.sh ./

ENTRYPOINT ["./entrypoint.sh"]
#CMD ["/data/weewx.conf"]
