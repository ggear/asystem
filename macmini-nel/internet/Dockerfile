FROM telegraf:1.16.0

RUN apt-get update && apt-get -y --no-install-recommends install \
  python2.7=2.7.16-2+deb10u1 \
  python-pip=18.1-5 \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 pip install && rm -rf /asystem/reqs_run.txt
COPY src/main/python/internet.py /asystem

ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
