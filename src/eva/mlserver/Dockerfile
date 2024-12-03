ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION=""

FROM python:${ASYSTEM_PYTHON_VERSION}${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION} AS image_upstream

ARG ASYSTEM_MLFLOW_VERSION
ARG ASYSTEM_MLSERVER_VERSION

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u8 && \
    apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/config && mkdir -p /asystem/data
COPY src/.py_deps.txt /asystem/bin/
COPY src/main/resources/config/ /asystem/config/

FROM image_base AS image_build
RUN (python3 -m ensurepip 2> /dev/null || true) && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade mlflow==${ASYSTEM_MLFLOW_VERSION} && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade --ignore-requires-python mlserver==${ASYSTEM_MLSERVER_VERSION} && \
    pip3 cache purge && \
    apt-get -y remove build-essential && \
    apt-get -y purge

FROM image_build AS image_runtime
COPY src/main/resources/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
