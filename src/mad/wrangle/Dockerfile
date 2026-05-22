# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL="slim"
FROM python:${ASYSTEM_PYTHON_VERSION}-${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL} AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b13 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install coreutils=9.1-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install poppler-utils=22.12.0-2+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libc6-dev=2.36-9+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install zlib1g-dev=1:1.2.13.dfsg-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libssl-dev=3.0.20-1~deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libbz2-dev=1.0.8-5+b1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libffi-dev=3.4.4-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install liblzma-dev=5.4.1-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libsqlite3-dev=3.40.1-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libreadline-dev=8.2-1.3 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libncurses5-dev=6.4-4 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libncursesw5-dev=6.4-4 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libpoppler-cpp-dev=22.12.0-2+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
ENV PYTHONUTF8=1
ENV PYTHONUNBUFFERED=1
COPY src/main/python/.py_deps.txt /asystem/bin/python/.py_deps.txt
COPY target/package/main/resources/image/. /asystem/etc
RUN set -eux; \
    if [ -f /asystem/bin/python/.py_deps.txt ]; then pip3 install --default-timeout=1000 --no-cache-dir -r /asystem/bin/python/.py_deps.txt; fi; \
    pip3 cache purge; \
    mkdir -p /root/.config/gspread_pandas; \
    cp -rf /asystem/etc/.gspread_pandas/. /root/.config/gspread_pandas/; \
    cp -rf /asystem/etc/.google_service_account.json /root;

FROM image_base AS image_build
COPY target/package/main/python/. /asystem/bin/python
RUN set -eux; \
    pip3 install --default-timeout=1000 --no-cache-dir /asystem/bin/python; \
    pip3 cache purge;

FROM image_build AS image_runtime
WORKDIR /asystem/etc
ENTRYPOINT ["wrangle"]
