ARG ASYSTEM_TELEGRAF_VERSION="latest"

FROM telegraf:${ASYSTEM_TELEGRAF_VERSION} AS image_base

ARG ASYSTEM_PYTHON_VERSION
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

FROM image_base AS image_package
USER root
RUN apt-get update && \
    apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2 && \
    apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    apt-get -y --no-install-recommends --allow-downgrades install poppler-utils=22.12.0-2+b1 && \
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
    apt-get -y --no-install-recommends --allow-downgrades install libpoppler-cpp-dev=22.12.0-2+b1 && \
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

FROM image_install AS image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/main/python/ src/.py_deps.txt /asystem/
RUN pip3 install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade -r /asystem/.py_deps.txt && \
    rm -rf /asystem/.py_deps.txt && \
    mkdir -p /root/.config && \
    mkdir -p /etc/telegraf/.config
COPY src/main/resources/.gspread_pandas /root/.config/gspread_pandas
COPY src/main/resources/.google_service_account.json /root
COPY src/main/resources/.gspread_pandas /etc/telegraf/.config/gspread_pandas
COPY src/main/resources/.google_service_account.json /etc/telegraf
COPY src/main/resources/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
