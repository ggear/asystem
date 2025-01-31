ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION=""

# Defined: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
FROM python:${ASYSTEM_PYTHON_VERSION}${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION} AS image_upstream

ARG ASYSTEM_MLFLOW_VERSION

FROM image_upstream AS image_base
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b7 && \
    apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u8 && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2 && \
    apt-get -y --no-install-recommends --allow-downgrades install git=1:2.39.5-0+deb12u2 && \
    apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt
COPY target/package/main/resources/image /asystem/etc

FROM image_base AS image_build
USER root
RUN \
    apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
RUN (python3 -m ensurepip 2> /dev/null || true) && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade virtualenv==20.27.1 && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade psycopg2-binary==2.9.10  && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade mlflow[extras]==${ASYSTEM_MLFLOW_VERSION} && \
    pip3 cache purge
ENV PATH=/root/.pyenv/bin:$PATH
RUN cd /tmp && \
    rm -rf pyenv && \
    git clone https://github.com/pyenv/pyenv.git &&  \
    cd /tmp/pyenv &&  \
    git checkout v2.4.17 && \
    ./src/configure &&  \
    make -C src && \
    rm -rf /root/.pyenv && \
    mkdir -p /root/.pyenv && \
    mv bin libexec /root/.pyenv && \
    cd /root && \
    pyenv --version && \
    rm -rf /tmp/* && \
    apt-get -y remove git && \
    apt-get -y remove build-essential && \
    apt-get -y purge

FROM image_build AS image_runtime
ENTRYPOINT ["/asystem/etc/entrypoint.sh"]
