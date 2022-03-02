#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

add_on_boot_script() {
  [ ! -f "/mnt/data/on_boot.d/${1}.sh" ] &&
    [ -d "/var/lib/asystem/install" ] &&
    [ -f "$(ls -td /var/lib/asystem/install/*udm-rack*/${2}/* | head -1)/run.sh" ] &&
    cp -rvf "$(ls -td /var/lib/asystem/install/*udm-rack*/${2}/* | head -1)/run.sh" "/mnt/data/on_boot.d/${1}.sh"
}

cd ${SERVICE_INSTALL} || exit

chmod a+x ./config/udm-utilities/on-boot-script/remote_install.sh
if [ ! -d /mnt/data/on_boot.d ]; then
  ./config/udm-utilities/on-boot-script/remote_install.sh
fi

chmod a+x ./config/udm-utilities/container-common/on_boot.d/05-container-common.sh
if [ ! -f /mnt/data/on_boot.d/05-container-common.sh ]; then
  cp -rvf ./config/udm-utilities/container-common/on_boot.d/05-container-common.sh /mnt/data/on_boot.d
  /mnt/data/on_boot.d/05-container-common.sh
fi

add_on_boot_script "10-unifios" "_unifios"
add_on_boot_script "11-users" "_users"
add_on_boot_script "12-links" "_links"

podman exec unifi-os systemctl enable udm-boot
podman exec unifi-os systemctl restart udm-boot
