#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

add_on_boot_script() {
  [ ! -f "/mnt/data/on_boot.d/${1}.sh" ] &&
    [ -d "/var/lib/asystem/install" ] &&
    [ -f "/var/lib/asystem/install/*udm-rack*/${2}/latest/run.sh" ] &&
    cp -rvf "/var/lib/asystem/install/*udm-rack*/${2}/latest/run.sh" "/mnt/data/on_boot.d/${1}.sh"
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

chmod a+x ./config/udm-host-records/*.sh
rm -rf /mnt/data/udm-host-records && cp -rvf ./config/udm-host-records /mnt/data

chmod a+x ./config/udm-dnsmasq/01-dnsmasq.sh
rm -rf /mnt/data/udm-dnsmasq && cp -rvf ./config/udm-dnsmasq /mnt/data
cp -rvf ./config/udm-dnsmasq/01-dnsmasq.sh /mnt/data/on_boot.d
/mnt/data/on_boot.d/01-dnsmasq.sh

cp -rvf ./config/udm-utilities/cni-plugins/05-install-cni-plugins.sh /mnt/data/on_boot.d
chmod a+x /mnt/data/on_boot.d/05-install-cni-plugins.sh
/mnt/data/on_boot.d/05-install-cni-plugins.sh
cp -rvf ./config/udm-utilities/cni-plugins/20-dns.conflist /etc/cni/net.d
podman network rm dns 2>/dev/null && podman network create dns
cp -rvf ./config/udm-utilities/dns-common/10-dns.sh /mnt/data/on_boot.d
chmod a+x /mnt/data/on_boot.d/10-dns.sh
/mnt/data/on_boot.d/10-dns.sh
mkdir -p /mnt/data/etc-pihole
mkdir -p /mnt/data/pihole/etc-dnsmasq.d
