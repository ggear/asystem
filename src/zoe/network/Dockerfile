# https://hub.docker.com/_/golang/tags?page=1&ordering=last_updated&name=-alpine
ARG GO_VERSION

FROM golang:$GO_VERSION-alpine AS image_base

FROM image_base AS image_package

FROM image_package AS image_install
COPY src/main/go/ /asystem/
WORKDIR /asystem/pkg
RUN go build
WORKDIR /asystem/cmd
RUN go install

FROM image_install AS image_runtime

ENTRYPOINT ["cmd"]
CMD ["--period=1200"]
