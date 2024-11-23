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
    PKG_CLEAN="apt-get clean"
  [[ "$(which apk)" != "" ]] &&
    PKG="apk" &&  
    PKG_UPDATE="apk update" &&
    PKG_BOOTSTRAP="apk add --no-cache util-linux" &&
    PKG_VERSION="apk version" &&
    PKG_VERSION_GREP="=" &&
    PKG_VERSION_AWK='{print $3}' &&    
    PKG_INSTALL="apk add --no-cache" &&
    PKG_CLEAN="apk cache clean"
  [[ ${PKG} == "" ]] && echo "Cannot identify package manager, bailing out!" && exit 1
  ASYSTEM_PACKAGES=(
    mosquitto-clients
  )
  set -x
  ${PKG_UPDATE}
  ${PKG_BOOTSTRAP}
  for ASYSTEM_PACKAGE in "${ASYSTEM_PACKAGES[@]}"; do ${PKG_INSTALL} "${ASYSTEM_PACKAGE}" 2>/dev/null; done
  set +x
  sleep 1
  echo "#######################################################################################"
  echo "Base image package install command:"
  echo "#######################################################################################" && echo ""
  echo "USER root"
  echo -n "RUN "
  [[ "${PKG_UPDATE}" != "" ]] && echo -n "${PKG_UPDATE}"
  echo " && \\"
  for ASYSTEM_PACKAGE in "${ASYSTEM_PACKAGES[@]}"; do echo "    ${PKG_INSTALL}" "${ASYSTEM_PACKAGE}="$(${PKG_VERSION} ${ASYSTEM_PACKAGE} 2>/dev/null | grep "${PKG_VERSION_GREP}" | column -t | awk "${PKG_VERSION_AWK}")" && \\"; done
  echo "    ${PKG_CLEAN}" && echo ""
  echo "#######################################################################################"
  echo "Base image run command:"
  echo "#######################################################################################" && echo ""
  echo "docker run -it --rm --user root --entrypoint bash \\
    -e ASYSTEM_PYTHON_VERSION=3.12.7 \\
    -e ASYSTEM_GO_VERSION=1.21.6 \\
    -e ASYSTEM_RUST_VERSION=1.75.0 \\
    -e ASYSTEM_MLFLOW_VERSION=2.18.0 \\
    -e ASYSTEM_MLSERVER_VERSION=1.6.1 \\
    -e ASYSTEM_TELEGRAF_VERSION=1.32.3 \\
    -e ASYSTEM_HOMEASSISTANT_VERSION=2024.11.1 \\
    'library/telegraf:1.32.3'" && echo ""
  echo "#######################################################################################"
}
declare -f echo_package_install_commands | sed '1,2d;$d' | docker run --user root --entrypoint bash -i --rm 'library/telegraf:1.32.3' -