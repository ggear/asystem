ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION=""

FROM python:${ASYSTEM_PYTHON_VERSION}${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION} AS image_base

ARG ASYSTEM_MLFLOW_VERSION
ARG ASYSTEM_MLSERVER_VERSION

FROM image_base AS image_package
USER root
RUN apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u8 && \
    apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    apt-get clean

FROM image_package AS image_install
RUN pip cache dir && \
    pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade mlflow==${ASYSTEM_MLFLOW_VERSION} && \
    pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade --ignore-requires-python mlserver==${ASYSTEM_MLSERVER_VERSION} && \
    pip cache purge && \
    apt-get -y remove build-essential && \
    apt-get -y purge

FROM image_install AS image_runtime
COPY src/main/resources/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
