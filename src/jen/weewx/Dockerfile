# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL="slim"
FROM python:${ASYSTEM_PYTHON_VERSION}-${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL} AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b9 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install apache2=2.4.65-1~deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install mosquitto-clients=2.0.11-1.2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN set -eux; \
    python3 -m ensurepip 2> /dev/null; \
    pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir --upgrade pip; \
    pip3 cache purge

FROM image_base AS image_build
COPY src/main/python/. /asystem/bin/python
COPY target/package/main/resources/image/. /asystem/etc
RUN set -eux; \
    pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir --upgrade -r /asystem/bin/python/.py_deps.txt; \
    pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir /asystem/etc/install/weewx*.whl; \
    pip3 cache purge; \
    mkdir -p /etc/weewx; \
    rm -rf /etc/weewx/weewx.conf* /var/www/html /data/html/loopdata/*; \
    cp -f /asystem/etc/config/weewx.conf /etc/weewx/; \
    cp -f /asystem/etc/config/apache2.conf /etc/apache2/; \
    weectl extension install -y /asystem/etc/install/weewx-mqtt.zip; \
    sed -i '/#   openssl s_client -help/d' /home/weewx/bin/user/mqtt.py; \
    weectl extension install -y /asystem/etc/install/weewx-loopdata.zip; \
    rm -rf /asystem/etc/install/weewx*.whl /asystem/etc/install/weewx-mqtt.zip /asystem/etc/install/weewx-loopdata.zip; \
    mkdir -p /data/html; \
    touch /data/html/index.html; \
    ln -s /data/html /var/www/html

FROM image_build AS image_runtime
ENV WEEWX_HOME="/home/weewx"
WORKDIR /asystem/etc
ENTRYPOINT ["/asystem/etc/entrypoint.sh"]
