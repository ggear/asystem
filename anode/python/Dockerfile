FROM python:2.7-slim-stretch as base
FROM base as builder

RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt
RUN apt-get update && apt-get -y install pkg-config build-essential libfreetype6-dev libffi-dev libpng-dev && apt-get clean && apt-get purge
RUN cat /requirements.txt | xargs -n 1 pip install --no-deps --prefix=/install

FROM base
COPY --from=builder /install /usr/local
COPY src /app

WORKDIR /app

CMD ["anode"]
