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
ENV GOROOT /usr/lib/go
ENV GOPATH /go
ENV PATH /go/bin:$PATH
RUN mkdir -p ${GOPATH}/src ${GOPATH}/bin
RUN go get -u github.com/Masterminds/glide/...

FROM image_install as image_runtime
RUN mkdir -p /bootstrap
COPY src/main/resources/libraries /bootstrap
WORKDIR /bootstrap/grizzly
RUN make dev
COPY src/main/resources/config/dashboards/template/private /bootstrap/dashboards

ENTRYPOINT [ "/run.sh" ]
