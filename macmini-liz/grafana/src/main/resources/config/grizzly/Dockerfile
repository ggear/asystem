FROM golang
WORKDIR /app
COPY . .
RUN make install

FROM alpine
COPY --from=0 /go/bin/grr /usr/local/bin/grr
ENTRYPOINT ["/usr/local/bin/grr"]
