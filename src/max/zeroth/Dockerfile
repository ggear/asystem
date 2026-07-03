# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
ARG ASYSTEM_PYTHON_VERSION="latest"
ARG ASYSTEM_RUST_VERSION="latest"
ARG ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION="slim"
FROM debian:${ASYSTEM_IMAGE_VARIANT_DEBIAN_SLIM_VERSION} AS image_upstream
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install bash=5.2.15-2+b10 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install coreutils=9.1-1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install less=590-2.1~deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install curl=7.88.1-10+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install vim=2:9.0.1378-2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install jq=1.6-2.1+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install mosquitto-clients=2.0.11-1.2+deb12u2 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt

FROM image_upstream AS image_base
ARG ASYSTEM_RUST_VERSION
ENV CARGO_HOME=/asystem/bin/rust
ENV RUSTUP_HOME=/asystem/bin/rust
ENV PATH=/asystem/bin/rust/bin:${PATH}
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install ca-certificates=20230311+deb12u1 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install gcc=4:12.2.0-3 && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --allow-downgrades install libc6-dev=2.36-9+deb12u14 && \
    DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/* && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --no-modify-path --profile minimal --default-toolchain "${ASYSTEM_RUST_VERSION}"
COPY src/main/rust/zeroth /asystem/bin/zeroth
RUN cd /asystem/bin/zeroth && cargo build --release --locked

FROM image_upstream AS image_runtime
COPY --from=image_base /asystem/bin/zeroth/target/release/zeroth /asystem/bin/zeroth
WORKDIR /asystem/etc
CMD ["/asystem/bin/zeroth", "--poll-period", "60s"]
