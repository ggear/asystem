# https://github.com/greghesp/assistant-relay/releases
FROM node:10.24 as image_base

ENV ASSISTANTRELAY_VERSION="v3.2.0"
ENV ASSISTANTRELAY_HOME="/home/assistant-relay"

FROM image_base as image_package
RUN npm i pm2 -g

FROM image_package as image_install
RUN mkdir -p ${ASSISTANTRELAY_HOME}/bin
WORKDIR ${ASSISTANTRELAY_HOME}
RUN wget https://github.com/greghesp/assistant-relay/releases/download/${ASSISTANTRELAY_VERSION}/release.zip \
    && unzip release.zip \
    && rm release.zip \
    && npm i

FROM image_install as image_runtime
COPY src/main/resources/entrypoint.sh ./

EXPOSE 3000
VOLUME ["/data"]

ENTRYPOINT ["./entrypoint.sh"]
