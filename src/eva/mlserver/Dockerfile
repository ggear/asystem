FROM debian:12.8-slim AS image_base

ARG ASYSTEM_PYTHON_VERSION
ARG ASYSTEM_MLFLOW_VERSION
ARG ASYSTEM_MLSERVER_VERSION

FROM image_base AS image_package
USER root
RUN apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u8 && \
    apt-get -y --no-install-recommends --allow-downgrades install wget=1.21.3-1+b2 && \
    apt-get -y --no-install-recommends --allow-downgrades install ca-certificates=20230311 && \
    apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    apt-get -y --no-install-recommends --allow-downgrades install libc6-dev=2.36-9+deb12u9 && \
    apt-get -y --no-install-recommends --allow-downgrades install zlib1g-dev=1:1.2.13.dfsg-1 && \
    apt-get -y --no-install-recommends --allow-downgrades install libssl-dev=3.0.15-1~deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install libbz2-dev=1.0.8-5+b1 && \
    apt-get -y --no-install-recommends --allow-downgrades install libffi-dev=3.4.4-1 && \
    apt-get -y --no-install-recommends --allow-downgrades install liblzma-dev=5.4.1-0.2 && \
    apt-get -y --no-install-recommends --allow-downgrades install libsqlite3-dev=3.40.1-2+deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install libreadline-dev=8.2-1.3 && \
    apt-get -y --no-install-recommends --allow-downgrades install libncurses5-dev=6.4-4 && \
    apt-get -y --no-install-recommends --allow-downgrades install libncursesw5-dev=6.4-4 && \
    apt-get clean

FROM image_package AS image_install
RUN cd /tmp && \
    rm -f Python* && \
    wget https://www.python.org/ftp/python/$ASYSTEM_PYTHON_VERSION/Python-$ASYSTEM_PYTHON_VERSION.tgz && \
    tar zxf Python-$ASYSTEM_PYTHON_VERSION.tgz && \
    cd /tmp/Python-$ASYSTEM_PYTHON_VERSION && \
    ./configure --prefix=/usr/local && \
    make && \
    make install && \
    cd /root && \
    python3 --version && \
    pip3 --version && \
    rm -rf /tmp/*
RUN pip3 cache dir && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade --ignore-requires-python mlflow==${ASYSTEM_MLFLOW_VERSION} && \
    pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade --ignore-requires-python mlserver==${ASYSTEM_MLSERVER_VERSION} && \
    pip3 cache purge

FROM image_install AS image_runtime
COPY src/main/resources/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
