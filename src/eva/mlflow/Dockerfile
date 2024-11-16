# https://github.com/mlflow/mlflow/pkgs/container/mlflow
FROM ghcr.io/mlflow/mlflow:v2.17.2 AS image_base

FROM image_base AS image_package
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apt-get update
RUN apt-get -y --no-install-recommends install build-essential=12.9
RUN apt-get -y --no-install-recommends install pkg-config=0.29.2-1
RUN apt-get -y --no-install-recommends install procps=2:3.3.17-5
RUN apt-get -y --no-install-recommends install git=1:2.30.2-1+deb11u3
RUN apt-get -y --no-install-recommends install vim=2:8.2.2434-3+deb11u1
RUN apt-get -y --no-install-recommends install llvm=1:11.0-51+nmu5
RUN apt-get -y --no-install-recommends install curl=7.74.0-1.3+deb11u13
RUN apt-get -y --no-install-recommends install wget=1.21-1+deb11u1
RUN apt-get -y --no-install-recommends install zlib1g-dev=1:1.2.11.dfsg-2+deb11u2
RUN apt-get -y --no-install-recommends install libssl-dev=1.1.1w-0+deb11u2
RUN apt-get -y --no-install-recommends install libbz2-dev=1.0.8-4
RUN apt-get -y --no-install-recommends install libreadline-dev=8.1-1
RUN apt-get -y --no-install-recommends install libsqlite3-dev=3.34.1-3+deb11u1
RUN apt-get -y --no-install-recommends install libncurses5-dev=6.2+20201114-2+deb11u2
RUN apt-get -y --no-install-recommends install libncursesw5-dev=6.2+20201114-2+deb11u2
RUN apt-get -y --no-install-recommends install xz-utils=5.2.5-2.1~deb11u1
RUN apt-get -y --no-install-recommends install tk-dev=8.6.11+1
RUN apt-get -y --no-install-recommends install libffi-dev=3.3-6
RUN apt-get -y --no-install-recommends install liblzma-dev=5.2.5-2.1~deb11u1

RUN git clone https://github.com/pyenv/pyenv.git /root/.pyenv &&  \
    cd /root/.pyenv &&  \
    git checkout v2.4.3 && \
    ./src/configure &&  \
    make -C src &&  \
    echo $'export PATH=$PATH:/root/.pyenv/bin\n' >>/root/.bashrc

FROM image_package AS image_install
RUN pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir --upgrade pip
#RUN pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir pyopenssl==24.2.1
RUN pip install --root-user-action ignore --default-timeout=1000 --no-cache-dir psycopg2-binary==2.9.10

FROM image_install AS image_runtime

COPY src/main/resources/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
