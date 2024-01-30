#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

chmod a+x ./config/udm-utilities/on-boot-script/remote_install.sh
if [ ! -d /data/on_boot.d ]; then
  ./config/udm-utilities/on-boot-script/remote_install.sh
fi

cp -rvf /data/asystem/install/udmutilities/latest/install_prep.sh /data/on_boot.d/07-asystem-install.sh
chmod a+x /data/on_boot.d/07-asystem-install.sh

add_on_boot_script() {
  [ ! -f "/data/on_boot.d/${1}.sh" ] &&
    [ -d "/var/lib/asystem/install" ] &&
    [ -f "/var/lib/asystem/install/${2}/latest/install.sh" ] &&
    cp -rvf "/var/lib/asystem/install/${2}/latest/install.sh" "/data/on_boot.d/${1}.sh"
}
add_on_boot_script "10-unifios" "_unifios"
add_on_boot_script "11-users" "_users"
add_on_boot_script "12-links" "_links"

chmod a+x ./config/udm-certificates/20-certifcates.sh
cp -rvf ./config/udm-certificates/20-certifcates.sh /data/on_boot.d
/data/on_boot.d/20-certifcates.sh

chmod a+x ./config/udm-dnsmasq/24-dnsmasq.sh
rm -rf /data/udm-dnsmasq && cp -rvf ./config/udm-dnsmasq /data
cp -rvf ./config/udm-dnsmasq/24-dnsmasq.sh /data/on_boot.d
#/data/on_boot.d/24-dnsmasq.sh

#cp -rvf ./config/udm-cloudflare-ddns/28-cloudflare-ddns.sh /data/on_boot.d
#chmod a+x /data/on_boot.d/28-cloudflare-ddns.sh
#/data/on_boot.d/28-cloudflare-ddns.sh

# INFO: Disable podman services since it has been depracted since udm-pro-3
#chmod a+x ./config/udm-utilities/container-common/on_boot.d/05-container-common.sh
#if [ ! -f /data/on_boot.d/05-container-common.sh ]; then
#  cp -rvf ./config/udm-utilities/container-common/on_boot.d/05-container-common.sh /data/on_boot.d
#  /data/on_boot.d/05-container-common.sh
#fi
#
#podman exec unifi-os systemctl enable udm-boot
#podman exec unifi-os systemctl restart udm-boot
#
#cp -rvf ./config/udm-utilities/cni-plugins/05-install-cni-plugins.sh /data/on_boot.d
#chmod a+x /data/on_boot.d/05-install-cni-plugins.sh
#/data/on_boot.d/05-install-cni-plugins.sh
#cp -rvf ./config/udm-utilities/cni-plugins/20-dns.conflist /data/podman/cni
#
#mkdir -p /data/etc-pihole && chmod 777 /data/etc-pihole
#mkdir -p /data/pihole/etc-dnsmasq.d && chmod 777 /data/pihole/etc-dnsmasq.d
#if [ ! -f /data/pihole/etc-dnsmasq.d/02-custom.conf ]; then
#  cat <<EOF >>/data/pihole/etc-dnsmasq.d/02-custom.conf
#rev-server=10.0.0.0/8,10.0.0.1
#server=/janeandgraham.com/10.0.0.1
#server=//10.0.0.1
#EOF
#  chmod 644 /data/pihole/etc-dnsmasq.d/02-custom.conf
#fi
#podman stop pihole 2>/dev/null
#podman rm pihole 2>/dev/null
#podman create --network dns --restart always \
#  --name pihole \
#  -e TZ="Australia/Perth" \
#  -v "/data/etc-pihole/:/etc/pihole/" \
#  -v "/data/pihole/etc-dnsmasq.d/:/etc/dnsmasq.d/" \
#  --dns=127.0.0.1 \
#  --dns=1.1.1.1 \
#  --dns=8.8.8.8 \
#  --hostname udm-pihole \
#  -e VIRTUAL_HOST="udm-pihole" \
#  -e PROXY_LOCATION="udm-pihole" \
#  -e ServerIP="${PIHOLE_IP}" \
#  -e IPv6="False" \
#  pihole/pihole:2023.02.2
#cp -rvf ./config/udm-utilities/dns-common/on_boot.d/10-dns.sh /data/on_boot.d
#chmod a+x /data/on_boot.d/10-dns.sh
#/data/on_boot.d/10-dns.sh
#podman exec -it pihole pihole -a -p ${PIHOLE_KEY}
