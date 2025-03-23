ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL="slim"

FROM python:${ASYSTEM_PYTHON_VERSION}-${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL} AS image_upstream

ARG ASYSTEM_WEEWX_VERSION

ENV WEEWX_HOME="/home/weewx"
ENV PYTHONDONTWRITEBYTECODE=1

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b7 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u12 && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install apache2=2.4.62-1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install mosquitto-clients=2.0.11-1.2+deb12u1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY src/main/python /asystem/bin/python
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build
RUN \
    (python3 -m ensurepip 2> /dev/null || true) && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade -r /asystem/bin/python/.py_deps.txt && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir /asystem/etc/bin/weewx*.whl && \
    pip3 cache purge
RUN \
    mkdir -p "${WEEWX_HOME}" && \
    find "${WEEWX_HOME}" -type f -delete && \
    rm -rf $(pip show weewx | grep Location | sed 's/Location: //')/weewx_data && \
    ln -s $(pip show weewx | grep Location | sed 's/Location: //')/weewx_data "${WEEWX_HOME}" && \
    mkdir -p /etc/weewx && \
    rm -rf /etc/weewx/weewx.conf* && \
    cp -rf /asystem/etc/config/weewx.conf /etc/weewx && \
    weectl extension install -y /asystem/etc/bin/weewx-mqtt.zip && \
    sed -i "s/\\-/\\\\-/g" /home/weewx/bin/user/mqtt.py
RUN \
    mkdir -p /data/html && \
    touch /data/html/index.html && \
    rm -rf /var/www/html && \
    ln -s /data/html /var/www/html && \
    cp -rf /asystem/etc/config/apache2.conf /etc/apache2

FROM image_build AS image_runtime
ENTRYPOINT ["/asystem/etc/entrypoint.sh"]
