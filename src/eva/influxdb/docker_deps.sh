#!/bin/bash
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
function echo_package_install_commands {
  set -e
  set -o pipefail
  [[ "$(which apt-get)" != "" ]] &&
    PKG="apt-get" &&
    PKG_UPDATE="apt-get update" &&
    PKG_BOOTSTRAP="apt-get -y install bsdmainutils" &&
    PKG_VERSION="apt show" &&
    PKG_VERSION_GREP="Version" &&
    PKG_VERSION_AWK='{print $2}' &&
    PKG_INSTALL="apt-get -y --no-install-recommends --allow-downgrades install" &&
    PKG_CLEAN="apt-get clean && rm -rf /var/lib/apt/lists/*"
  [[ "$(which apk)" != "" ]] &&
    PKG="apk" &&
    PKG_UPDATE="apk update" &&
    PKG_BOOTSTRAP="apk add --no-cache util-linux" &&
    PKG_VERSION="apk version" &&
    PKG_VERSION_GREP="=" &&
    PKG_VERSION_AWK='{print $3}' &&
    PKG_INSTALL="apk add --no-cache" &&
    PKG_CLEAN="apk cache clean && rm -rf /var/cache/apk/*"
  [[ $PKG == "" ]] && echo "Cannot identify package manager, bailing out!" && exit 1
  ASYSTEM_PACKAGES_BASE=(
    bash
    less
    curl
    vim
    jq
  )
  ASYSTEM_PACKAGES_BUILD=(
    bash
  )
  set -x
  $PKG_UPDATE
  $PKG_BOOTSTRAP
  for ASYSTEM_PACKAGE in "${ASYSTEM_PACKAGES_BASE[@]}"; do $PKG_INSTALL "$ASYSTEM_PACKAGE" 2>/dev/null; done
  for ASYSTEM_PACKAGE in "${ASYSTEM_PACKAGES_BUILD[@]}"; do $PKG_INSTALL "$ASYSTEM_PACKAGE" 2>/dev/null; done
  set +x
  sleep 1
  cat <<EOF >"/tmp/base_image_install.sh"
ASYSTEM_PACKAGES_BASE=(
    bash
    less
    curl
    vim
    jq
)
ASYSTEM_PACKAGES_BUILD=(
    bash
)
echo "#######################################################################################"
echo "# Base image package install command:"
echo "#######################################################################################" && echo ""
echo "USER root"
echo "RUN \\\\"
[[ "$PKG_UPDATE" != "" ]] && echo -n "    $PKG_UPDATE"
echo " && \\\\"
for ASYSTEM_PACKAGE in "\${ASYSTEM_PACKAGES_BASE[@]}"; do echo "    $PKG_INSTALL" "\$ASYSTEM_PACKAGE="\$($PKG_VERSION \$ASYSTEM_PACKAGE 2>/dev/null | grep "$PKG_VERSION_GREP" | column -t | awk '$PKG_VERSION_AWK')" && \\\\"; done
echo "    $PKG_CLEAN && \\\\"
echo "    mkdir -p /asystem/bin && mkdir -p /asystem/etc && mkdir -p /asystem/mnt"
echo "COPY src/main/resources/host /asystem/etc"
echo "#######################################################################################"
echo "# Build image package install command:"
echo "#######################################################################################" && echo ""
echo "USER root"
echo "RUN \\\\"
[[ "$PKG_UPDATE" != "" ]] && echo -n "    $PKG_UPDATE"
echo " && \\\\"
for ASYSTEM_PACKAGE in "\${ASYSTEM_PACKAGES_BUILD[@]}"; do echo "    $PKG_INSTALL" "\$ASYSTEM_PACKAGE="\$($PKG_VERSION \$ASYSTEM_PACKAGE 2>/dev/null | grep "$PKG_VERSION_GREP" | column -t | awk '$PKG_VERSION_AWK')" && \\\\"; done
echo "    $PKG_CLEAN && \\\\"
EOF
  cat <<EOF >"/tmp/base_image_run.sh"
echo ""
echo "#######################################################################################"
echo "# Base image run command:"
echo "#######################################################################################" && echo ""
echo "docker run -it --rm --user root --entrypoint sh \\\\"
echo "    -e ASYSTEM_PYTHON_VERSION=3.12.7 \\\\"
echo "    -e ASYSTEM_GO_VERSION=1.21.6 \\\\"
echo "    -e ASYSTEM_RUST_VERSION=1.75.0 \\\\"
echo "    -e ASYSTEM_WEEWX_VERSION=5.1.0 \\\\"
echo "    -e ASYSTEM_MLFLOW_VERSION=2.18.0 \\\\"
echo "    -e ASYSTEM_MLSERVER_VERSION=1.6.1 \\\\"
echo "    -e ASYSTEM_TELEGRAF_VERSION=1.32.3 \\\\"
echo "    -e ASYSTEM_HOMEASSISTANT_VERSION=2024.11.1 \\\\"
echo "    -e ASYSTEM_IMAGE_VARIANT_ALPINE_VERSION=-alpine \\\\"
echo "    -e ASYSTEM_IMAGE_VARIANT_UBUNTU_VERSION=-ubuntu \\\\"
echo "    -e ASYSTEM_IMAGE_VARIANT_DEBIAN_VERSION=-debian \\\\"
echo "    -e ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_VERSION=-bookworm \\\\"
echo "    -e ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION=-slim-bookworm \\\\"
echo "    'influxdb:2.7.10-alpine'" && echo ""
echo "#######################################################################################"
EOF
    chmod +x /tmp/base_image_*.sh
    /tmp/base_image_install.sh | grep -v '^USER' | grep -v '^RUN' | grep -v '^COPY' | bash -
    echo ""
    /tmp/base_image_install.sh
    /tmp/base_image_run.sh
}
DOCKER_CLI_HINTS=false
CONTAINER_NAME="asystem_deps_bootstrap"
docker ps -q --filter "name=$CONTAINER_NAME" | grep -q . && docker kill "$CONTAINER_NAME"
docker ps -qa --filter "name=$CONTAINER_NAME" | grep -q . && docker rm -vf "$CONTAINER_NAME"
docker run --name "$CONTAINER_NAME" --user root --entrypoint sh --mount type=bind,source=/Users/graham/Code/asystem/src/eva/influxdb/src/main/resources/host,target=/asystem/etc,readonly -dt 'influxdb:2.7.10-alpine'
docker exec -t "$CONTAINER_NAME" sh -c '[ "$(which apk)" != "" ] && apk add --no-cache bash; [ "$(which apt-get)" != "" ] && apt-get update && apt-get -y install bash'
declare -f echo_package_install_commands | sed '1,2d;$d' | docker exec -i "$CONTAINER_NAME" bash -
echo "Base image shell:" && echo "#######################################################################################" && echo ""
docker exec -it -e ASYSTEM_PYTHON_VERSION=3.12.7 -e ASYSTEM_GO_VERSION=1.21.6 -e ASYSTEM_RUST_VERSION=1.75.0 -e ASYSTEM_WEEWX_VERSION=5.1.0 -e ASYSTEM_MLFLOW_VERSION=2.18.0 -e ASYSTEM_MLSERVER_VERSION=1.6.1 -e ASYSTEM_TELEGRAF_VERSION=1.32.3 -e ASYSTEM_HOMEASSISTANT_VERSION=2024.11.1 -e ASYSTEM_IMAGE_VARIANT_ALPINE_VERSION=-alpine -e ASYSTEM_IMAGE_VARIANT_UBUNTU_VERSION=-ubuntu -e ASYSTEM_IMAGE_VARIANT_DEBIAN_VERSION=-debian -e ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_VERSION=-bookworm -e ASYSTEM_IMAGE_VARIANT_DEBIAN_CODENAME_SLIM_VERSION=-slim-bookworm "$CONTAINER_NAME" bash
docker kill "$CONTAINER_NAME"
docker rm -vf "$CONTAINER_NAME"