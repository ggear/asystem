# https://github.com/grafana/grafana/releases
FROM grafana/grafana:9.0.2 as image_base

FROM image_base as image_package
USER root
RUN apk add --no-cache \
  jq==1.6-r1 \
  git==2.34.4-r0 \
  curl==7.80.0-r2 \
  make==4.3-r0 \
  musl-dev==1.2.2-r7 \
  gcc==10.3.1_git20211027-r0 \
  go==1.17.10-r0

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