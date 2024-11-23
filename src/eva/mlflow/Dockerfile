ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION=""

FROM python:${ASYSTEM_PYTHON_VERSION}${ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION} AS image_base

ARG ASYSTEM_MLFLOW_VERSION

FROM image_base AS image_package
USER root
RUN apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2 && \
    apt-get -y --no-install-recommends --allow-downgrades install git=1:2.39.5-0+deb12u1 && \
    apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u8 && \
    apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    apt-get clean

FROM image_package AS image_install
RUN pip cache dir && \
    pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip && \
    pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade virtualenv==20.27.1 && \
    pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade psycopg2-binary==2.9.10  && \
    pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade mlflow[extras]==${ASYSTEM_MLFLOW_VERSION} && \
    pip cache purge
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

FROM image_install AS image_runtime
COPY src/main/resources/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
