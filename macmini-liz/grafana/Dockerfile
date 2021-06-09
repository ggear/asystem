FROM grafana/grafana:7.5.7 as image_base

FROM image_base as image_package
USER root
RUN apk add --no-cache \
  jq==1.6-r1 \
  git==2.26.3-r0 \
  curl==7.77.0-r0 \
  make==4.3-r0 \
  musl-dev==1.1.24-r10 \
  go==1.13.15-r0

FROM image_package as image_install
ARG GOLANG_VERSION=1.16.4
ENV GOROOT /usr/local/go
ENV GOPATH /go
ENV PATH=/usr/local/go/bin:$PATH
RUN wget https://dl.google.com/go/go$GOLANG_VERSION.src.tar.gz && tar -C /usr/local -xzf go$GOLANG_VERSION.src.tar.gz
RUN cd /usr/local/go/src && ./make.bash
RUN mkdir -p ${GOPATH}/src ${GOPATH}/bin
RUN rm go$GOLANG_VERSION.src.tar.gz
RUN apk del go

FROM image_install as image_runtime
RUN mkdir -p /bootstrap
COPY src/main/resources/libraries /bootstrap
WORKDIR /bootstrap/grizzly
RUN make dev
COPY src/main/resources/config/dashboards/instance /bootstrap/dashboards

ENTRYPOINT [ "/run.sh" ]
