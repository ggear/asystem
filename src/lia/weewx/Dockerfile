ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION=""

FROM python:${ASYSTEM_PYTHON_VERSION}${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION} AS image_upstream

ARG ASYSTEM_WEEWX_VERSION

ENV WEEWX_HOME="/home/weewx"
ENV PYTHONDONTWRITEBYTECODE=1

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install apache2=2.4.62-1~deb12u2 && \
    apt-get clean

FROM image_base AS image_build
COPY \
  src/.py_deps.txt \
  src/build/resources/weewx* \
  target/package/main/resources/config/weewx.conf \
  src/main/resources/apache2.conf \
  src/main/resources/entrypoint.sh \
  /asystem/
RUN \
    (python3 -m ensurepip 2> /dev/null || true) && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade -r /asystem/.py_deps.txt && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir /asystem/weewx*.whl && \
    pip3 cache purge
RUN \
    rm -rf "${WEEWX_HOME}" && \
    mkdir -p $(dirname "${WEEWX_HOME}") && \
    ln -s $(pip show weewx | grep Location | sed 's/Location: //')/weewx_data "${WEEWX_HOME}" && \
    mkdir -p /etc/weewx && \
    rm -rf /etc/weewx/weewx.conf* && \
    cp -rf /asystem/weewx.conf /etc/weewx && \
    weectl extension install -y /asystem/weewx-mqtt.zip
RUN \
    mkdir -p /data/html && \
    touch /data/html/index.html && \
    rm -rf /var/www/html && \
    ln -s /data/html /var/www/html && \
    cp -rf /asystem//apache2.conf /etc/apache2

FROM image_build AS image_runtime
WORKDIR "${WEEWX_HOME}"
EXPOSE 80
ENTRYPOINT ["/asystem/entrypoint.sh"]
