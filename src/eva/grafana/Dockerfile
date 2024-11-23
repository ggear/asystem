# https://github.com/grafana/grafana/releases
FROM grafana/grafana:10.0.5 AS image_base

FROM image_base AS image_package
USER root
RUN apk update && \
    apk add --no-cache jq=1.6-r4 && \
    apk add --no-cache git=2.40.3-r0 && \
    apk add --no-cache make=4.4.1-r1 && \
    apk add --no-cache gcc=12.2.1_git20220924-r10 && \
    apk add --no-cache musl-dev=1.2.4-r2 && \
    apk add --no-cache go=1.20.11-r0 && \
    apk cache clean

FROM image_package AS image_install
ARG GOLANG_VERSION=1.16.4
ENV GOROOT=/usr/local/go
ENV GOPATH=/go
ENV PATH=/usr/local/go/bin:$PATH
RUN cd /tmp && \
    rm -rf /tmp/go*.src.tar.gz && \
    wget https://dl.google.com/go/go$GOLANG_VERSION.src.tar.gz && \
    tar -C /usr/local -xzf go$GOLANG_VERSION.src.tar.gz &&  \
    cd /usr/local/go/src && \
    ./make.bash && \
    mkdir -p ${GOPATH}/src ${GOPATH}/bin && \
    apk del go && \
    cd /root && \
    go version && \
    rm -rf /tmp/go*.src.tar.gz

FROM image_install AS image_runtime
RUN mkdir -p /bootstrap
COPY src/main/resources/libraries /bootstrap
COPY src/main/resources/config/dashboards/instance /bootstrap/dashboards
WORKDIR /bootstrap/grizzly
RUN make dev
ENTRYPOINT [ "/run.sh" ]
