FROM python:2.7-slim-stretch as image_base

FROM image_base as image_package
RUN apt-get update && apt-get -y --no-install-recommends install \
  pkg-config=0.29-4+b1 \
  build-essential=12.3 \
  libfreetype6-dev=2.6.3-3.2+deb9u2 \
  libffi-dev=3.2.1-6 \
  libpng-dev=1.6.28-1+deb9u1 \
  tk=8.6.0+9 \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

FROM image_package as image_runtime
RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 pip install --no-deps --prefix=/asystem/runtime && rm -rf /asystem/reqs_run.txt

FROM image_runtime as image_install
RUN mkdir /asystem/install
WORKDIR /asystem/install
COPY src/reqs_dev.txt /asystem
RUN pip install -r /asystem/reqs_dev.txt
RUN mkdir /asystem/source
WORKDIR /asystem/source
COPY target/package /asystem/source
RUN export PYTHONPATH=/asystem/runtime/lib/python2.7/site-packages:/asystem/install/lib/python2.7/site-packages:$PYTHONPATH \
  && python setup.py install --prefix=/asystem/runtime

FROM image_runtime
COPY --from=image_install /asystem/runtime /usr/local

CMD ["anode", "--quiet"]
