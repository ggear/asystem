FROM telegraf:1.22.3 as image_base
       
FROM image_base as image_package
ARG PYTHON_VERSION
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get -y --no-install-recommends install \
  python3=$PYTHON_VERSION-3 \
  python3-dev=$PYTHON_VERSION-3 \
  python-is-python3=$PYTHON_VERSION-1 \
  python3-pip=20.3.4-4+deb11u1 \
  build-essential=12.9 \
  poppler-utils=20.09.0-3.1 \
  libpoppler-cpp-dev=20.09.0-3.1 \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_install
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 pip install && rm -rf /asystem/reqs_run.txt
RUN mkdir -p /root/.config
COPY src/main/resources/.gspread_pandas /root/.config/gspread_pandas
COPY src/main/resources/.google_service_account.json /root
RUN mkdir -p /etc/telegraf/.config
COPY src/main/resources/.gspread_pandas /etc/telegraf/.config/gspread_pandas
COPY src/main/resources/.google_service_account.json /etc/telegraf
COPY src/main/python/ /asystem/
COPY src/main/resources/entrypoint.sh /

FROM image_install as image_runtime
ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
