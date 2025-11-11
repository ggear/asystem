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
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install git=1:2.39.5-0+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_MLFLOW_VERSION
ARG ASYSTEM_MLSERVER_VERSION
RUN (python3 -m ensurepip 2> /dev/null || true) && \
    pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir --upgrade --ignore-requires-python mlserver==${ASYSTEM_MLSERVER_VERSION} && \
    pip3 cache purge && \
    apt-get -y remove build-essential && \
    apt-get -y purge

FROM image_base AS image_build
COPY src/main/python/. /asystem/bin/python
COPY target/package/main/resources/image/. /asystem/etc
RUN set -eux; \
    [ -f /asystem/bin/python/.py_deps.txt ] && pip3 install --root-user-action ignore --break-system-packages --default-timeout=1000 --no-cache-dir -r /asystem/bin/python/.py_deps.txt; \
    pip3 cache purge

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["/asystem/etc/entrypoint.sh"]
