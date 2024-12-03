# https://hub.docker.com/_/golang/tags?page=1&ordering=last_updated&name=-alpine
ARG ASYSTEM_GO_VERSION

FROM golang:$ASYSTEM_GO_VERSION-alpine AS image_upstream

FROM image_upstream AS image_base

FROM image_base AS image_build
COPY src/main/go/ /asystem/
WORKDIR /asystem/pkg
RUN go build
WORKDIR /asystem/cmd
RUN go install

FROM image_build AS image_runtime

ENTRYPOINT ["cmd"]
CMD ["--period=1200"]
