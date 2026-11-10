# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL="slim"
FROM python:${ASYSTEM_PYTHON_VERSION}-${ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_LABEL} AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b13 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install coreutils=9.1-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
ARG TARGETARCH
ARG ASYSTEM_GO_VERSION
ARG ASYSTEM_RUST_VERSION
ARG ASYSTEM_ONNXRUNTIME_VERSION
ENV PATH=/usr/local/go/bin:/root/.cargo/bin:${PATH}
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install ca-certificates=20250419~deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u15 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install build-essential=12.9 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://go.dev/dl/go${ASYSTEM_GO_VERSION}.linux-${TARGETARCH}.tar.gz" | tar -C /usr/local -xz && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal --default-toolchain "${ASYSTEM_RUST_VERSION}"
RUN ONNXRUNTIME_ARCH="$([ "${TARGETARCH}" = "arm64" ] && echo aarch64 || echo x64)" && \
    curl -fsSL "https://github.com/microsoft/onnxruntime/releases/download/v${ASYSTEM_ONNXRUNTIME_VERSION}/onnxruntime-linux-${ONNXRUNTIME_ARCH}-${ASYSTEM_ONNXRUNTIME_VERSION}.tgz" | tar -C /tmp -xz && \
    mkdir -p /build/onnxruntime && cp -L /tmp/onnxruntime-linux-${ONNXRUNTIME_ARCH}-${ASYSTEM_ONNXRUNTIME_VERSION}/lib/libonnxruntime.so /build/onnxruntime/libonnxruntime.so
COPY src/main/go/runtime /build/go
COPY src/main/rust/runtime /build/rust
RUN cd /build/go && go build -o /build/consumer-go . && \
    cd /build/rust && CARGO_TARGET_DIR=/build/target cargo build --release --locked && cp /build/target/release/consumer /build/consumer-rust

FROM image_upstream AS image_runtime
ARG PINS
RUN pip install --no-cache-dir ${PINS}
COPY --from=image_base /build/onnxruntime /asystem/bin/onnxruntime
COPY --from=image_base /build/consumer-go /asystem/bin/go
COPY --from=image_base /build/consumer-rust /asystem/bin/rust
COPY src/main/python/mlmodels/__init__.py /asystem/bin/python/mlmodels/__init__.py
COPY src/main/python/mlmodels/runtime /asystem/bin/python/mlmodels/runtime
ENV ONNXRUNTIME_LIB=/asystem/bin/onnxruntime/libonnxruntime.so
WORKDIR /asystem/bin/python
