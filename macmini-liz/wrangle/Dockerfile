FROM telegraf:1.18.3 as image_base
       
FROM image_base as image_package
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get -y --no-install-recommends install \
  python=2.7.16-1 \
  python-dev=2.7.16-1 \
  python-pip=18.1-5 \
  build-essential=12.6 \
  poppler-utils=0.71.0-5 \
  libpoppler-cpp-dev=0.71.0-5 && \
  apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_install
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 pip install && rm -rf /asystem/reqs_run.txt
RUN mkdir -p /root/.config
COPY src/main/resources/.gspread_pandas /root/.config/gspread_pandas
COPY src/main/resources/.google_service_account.json /root
COPY src/main/python/ /asystem/

FROM image_install as image_runtime
ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
