# https://github.com/grafana/grafana/releases
FROM grafana/grafana:10.0.5 as image_base

FROM image_base as image_package
USER root
# NOTE: To get package versions to pin: clear && docker image build . --progress=plain --no-cache 2>&1
RUN apk add --no-cache jq==1.6-r2
RUN apk add --no-cache git==2.38.5-r0
RUN apk add --no-cache curl==8.2.0-r1
RUN apk add --no-cache make==4.3-r1
RUN apk add --no-cache musl-dev==1.2.3-r5
RUN apk add --no-cache gcc==12.2.1_git20220924-r4
RUN apk add --no-cache go==1.19.9-r0

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