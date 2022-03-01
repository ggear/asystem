#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

chmod a+x ./config/udm-utilities/on-boot-script/remote_install.sh
./config/udm-utilities/on-boot-script/remote_install.sh

chmod a+x ./config/udm-utilities/container-common/on_boot.d/05-container-common.sh
cp -rvf ./config/udm-utilities/container-common/on_boot.d/05-container-common.sh /mnt/data/on_boot.d
/mnt/data/on_boot.d/05-container-common.sh

#[ -d "/var/lib/asystem/install" ] &&
#  [ -d "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)" ] &&
#  [ -f "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)/run.sh" ] &&
#  cp -rvf "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)/run.sh" /mnt/data/on_boot.d/keys.sh
