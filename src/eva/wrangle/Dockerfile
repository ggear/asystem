# https://github.com/influxdata/telegraf/releases
FROM telegraf:1.30.3 as image_base


FROM image_base as image_package
ARG PYTHON_VERSION
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install build-essential=12.9
RUN apt-get -y --no-install-recommends install libbz2-dev=1.0.8-5+b1
RUN apt-get -y --no-install-recommends install libffi-dev=3.4.4-1
RUN apt-get -y --no-install-recommends install zlib1g-dev=1:1.2.13.dfsg-1
RUN apt-get -y --no-install-recommends install libssl-dev=3.0.11-1~deb12u2
RUN apt-get -y --no-install-recommends install libsqlite3-dev=3.40.1-2
RUN apt-get -y --no-install-recommends install poppler-utils=22.12.0-2+b1
RUN apt-get -y --no-install-recommends install libpoppler-cpp-dev=22.12.0-2+b1
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_install
ARG PYTHON_VERSION
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN mkdir -p /tmp
WORKDIR /tmp
RUN wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz
RUN tar zxf Python-$PYTHON_VERSION.tgz
WORKDIR /tmp/Python-$PYTHON_VERSION
RUN ./configure --prefix=/usr/local
RUN make
RUN make install
RUN /usr/local/bin/python3 --version
RUN /usr/local/bin/python3 -m pip install --default-timeout=1000 --upgrade pip
RUN /usr/local/bin/pip3 --version
RUN rm -rf /tmp/*

FROM image_install as image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 /usr/local/bin/pip3 install --default-timeout=1000 && rm -rf /asystem/reqs_run.txt
RUN mkdir -p /root/.config
COPY src/main/resources/.gspread_pandas /root/.config/gspread_pandas
COPY src/main/resources/.google_service_account.json /root
RUN mkdir -p /etc/telegraf/.config
COPY src/main/resources/.gspread_pandas /etc/telegraf/.config/gspread_pandas
COPY src/main/resources/.google_service_account.json /etc/telegraf
COPY src/main/python/ /asystem/
COPY src/main/resources/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
