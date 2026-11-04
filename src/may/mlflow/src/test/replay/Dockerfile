ARG ASYSTEM_PYTHON_VERSION="latest"
FROM python:${ASYSTEM_PYTHON_VERSION}-slim
ARG TARGETARCH
ARG ASYSTEM_GO_VERSION
ARG ASYSTEM_RUST_VERSION
ENV PATH=/usr/local/go/bin:/root/.cargo/bin:$PATH
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends install bash curl ca-certificates build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://go.dev/dl/go${ASYSTEM_GO_VERSION}.linux-${TARGETARCH}.tar.gz" | tar -C /usr/local -xz
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain "${ASYSTEM_RUST_VERSION}"
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY rust /build/rust
RUN cd /build/rust && CARGO_TARGET_DIR=/build/target cargo build --release && mkdir -p /opt/modelreplay && cp /build/target/release/modelreplay /opt/modelreplay/rust
COPY go /build/go
RUN cd /build/go && go build -o /opt/modelreplay/go .
COPY parity.sh /opt/modelreplay/parity.sh
ENV PYTHONPATH=/asystem/build/python
ENV PARITY_RUST=/opt/modelreplay/rust
ENV PARITY_GO=/opt/modelreplay/go
ENTRYPOINT ["/opt/modelreplay/parity.sh"]
