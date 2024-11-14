# https://github.com/mlflow/mlflow/pkgs/container/mlflow
FROM ghcr.io/mlflow/mlflow:v2.17.2 AS image_base

FROM image_base AS image_package
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install build-essential=12.9
RUN apt-get -y --no-install-recommends install pkg-config=0.29.2-1
RUN apt-get -y --no-install-recommends install curl=7.74.0-1.3+deb11u13

FROM image_package AS image_install
RUN pip install --default-timeout=1000 --no-cache-dir --upgrade pip
RUN pip install --default-timeout=1000 --no-cache-dir psycopg2-binary==2.9.10

FROM image_install AS image_runtime

COPY src/main/resources/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
