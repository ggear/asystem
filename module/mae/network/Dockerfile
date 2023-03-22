# https://hub.docker.com/_/golang/tags?page=1&ordering=last_updated&name=-alpine
ARG GO_VERSION

FROM golang:$GO_VERSION-alpine as image_base

FROM image_base as image_package

FROM image_package as image_install
COPY src/main/go/ /asystem/
WORKDIR /asystem/pkg
RUN go build
WORKDIR /asystem/cmd
RUN go install

FROM image_install as image_runtime

ENTRYPOINT ["cmd"]
CMD ["--once=false"]
