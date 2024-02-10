# VERSION 1.0

FROM ubuntu:latest

MAINTAINER Jianshen Liu <jliu120@ucsc.edu>

RUN apt-get update \
    && apt-get install -y \
        build-essential \
        unzip \
        automake \
        libtool

ENV FOLDER_NAME sysbench
ENV VERSION 1.0

WORKDIR /root
ADD ${VERSION}.zip .
RUN unzip ${VERSION}.zip && rm ${VERSION}.zip

WORKDIR /root/${FOLDER_NAME}-${VERSION} 
RUN ./autogen.sh \
    && ./configure --without-mysql \
    && make

# Clean Up
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /root
COPY run.sh .
ENTRYPOINT ["./run.sh"]
