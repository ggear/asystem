FROM telegraf:1.16.2-alpine

ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache python2=2.7.18-r0 && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip install --upgrade pip setuptools && \
    rm -r /root/.cache

RUN mkdir -p /asystem/runtime
WORKDIR /asystem/runtime
COPY src/reqs_run.txt /asystem
RUN cat /asystem/reqs_run.txt | xargs -n 1 pip install && rm -rf /asystem/reqs_run.txt
COPY src/main/python/internet.py /asystem

ENTRYPOINT ["/entrypoint.sh"]
CMD ["telegraf"]
