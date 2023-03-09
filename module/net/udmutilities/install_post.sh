#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

add_on_boot_script() {
  [ ! -f "/mnt/data/on_boot.d/${1}.sh" ] &&
    [ -d "/var/lib/asystem/install" ] &&
    [ -f "/var/lib/asystem/install/*udm-net*/${2}/latest/install.sh" ] &&
    cp -rvf "/var/lib/asystem/install/${2}/latest/install.sh" "/mnt/data/on_boot.d/${1}.sh"
}

cd ${SERVICE_INSTALL} || exit

cp -rvf /mnt/data/asystem/install/udmutilities/latest/install_prep.sh /mnt/data/on_boot.d/20-asystem-install.sh
chmod a+x /mnt/data/on_boot.d/20-asystem-install.sh

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

chmod a+x ./config/udm-dnsmasq/09-dnsmasq.sh
rm -rf /mnt/data/udm-dnsmasq && cp -rvf ./config/udm-dnsmasq /mnt/data
cp -rvf ./config/udm-dnsmasq/09-dnsmasq.sh /mnt/data/on_boot.d
/mnt/data/on_boot.d/09-dnsmasq.sh

cp -rvf ./config/udm-utilities/cni-plugins/05-install-cni-plugins.sh /mnt/data/on_boot.d
chmod a+x /mnt/data/on_boot.d/05-install-cni-plugins.sh
/mnt/data/on_boot.d/05-install-cni-plugins.sh
cp -rvf ./config/udm-utilities/cni-plugins/20-dns.conflist /mnt/data/podman/cni

mkdir -p /mnt/data/etc-pihole && chmod 777 /mnt/data/etc-pihole
mkdir -p /mnt/data/pihole/etc-dnsmasq.d && chmod 777 /mnt/data/pihole/etc-dnsmasq.d
if [ ! -f /mnt/data/pihole/etc-dnsmasq.d/02-custom.conf ]; then
  cat <<EOF >>/mnt/data/pihole/etc-dnsmasq.d/02-custom.conf
rev-server=10.0.0.0/8,10.0.0.1
server=/local.janeandgraham.com/10.0.0.1
server=//10.0.0.1
EOF
  chmod 644 /mnt/data/pihole/etc-dnsmasq.d/02-custom.conf
fi
podman stop pihole 2>/dev/null
podman rm pihole 2>/dev/null
podman create --network dns --restart always \
  --name pihole \
  -e TZ="Australia/Perth" \
  -v "/mnt/data/etc-pihole/:/etc/pihole/" \
  -v "/mnt/data/pihole/etc-dnsmasq.d/:/etc/dnsmasq.d/" \
  --dns=127.0.0.1 \
  --dns=1.1.1.1 \
  --dns=8.8.8.8 \
  --hostname udm-pihole \
  -e VIRTUAL_HOST="udm-pihole" \
  -e PROXY_LOCATION="udm-pihole" \
  -e ServerIP="${PIHOLE_IP}" \
  -e IPv6="False" \
  pihole/pihole:2022.02.1
cp -rvf ./config/udm-utilities/dns-common/on_boot.d/10-dns.sh /mnt/data/on_boot.d
chmod a+x /mnt/data/on_boot.d/10-dns.sh
/mnt/data/on_boot.d/10-dns.sh
podman exec -it pihole pihole -a -p ${PIHOLE_KEY}

cp -rvf ./config/udm-cloudflare-ddns/13-cloudflare-ddns.sh /mnt/data/on_boot.d
chmod a+x /mnt/data/on_boot.d/13-cloudflare-ddns.sh
/mnt/data/on_boot.d/13-cloudflare-ddns.sh
