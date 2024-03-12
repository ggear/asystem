# https://github.com/Koenkk/zigbee2mqtt/releases
FROM koenkk/zigbee2mqtt:1.36.0 as image_base

FROM image_base as image_package
USER root
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apk add --no-cache mosquitto-clients==2.0.18-r0

FROM image_package as image_install
# NOTE: Overide python version given we are limitted by the zigbee2mqtt image
ENV PYTHON_VERSION=3.11.8-r0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN apk add --update --no-cache python3=$PYTHON_VERSION
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools
RUN pip3 install paho-mqtt==1.5.0

FROM image_install as image_runtime

ENTRYPOINT ["docker-entrypoint.sh"]
CMD [ "/sbin/tini", "--", "node", "index.js"]
