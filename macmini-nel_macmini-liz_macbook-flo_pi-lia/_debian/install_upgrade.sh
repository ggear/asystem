#!/bin/bash

################################################################################
# Upgrade system
################################################################################
echo "" && cat /etc/debian_version && echo ""
apt-get update
apt-get upgrade -y --without-new-pkgs
apt-get -y full-upgrade
apt-get -y --purge autoremove
echo "" && cat /etc/debian_version && echo ""

################################################################################
# Update repos
################################################################################
cat <<EOF >/etc/apt/sources.list
deb http://deb.debian.org/debian bullseye main contrib non-free
#deb-src http://deb.debian.org/debian bullseye main contrib non-free

deb http://deb.debian.org/debian-security/ bullseye-security main contrib non-free
#deb-src http://deb.debian.org/debian-security/ bullseye-security main contrib non-free

deb http://deb.debian.org/debian bullseye-updates main contrib non-free
#deb-src http://deb.debian.org/debian bullseye-updates main contrib non-free

deb http://deb.debian.org/debian bullseye-backports main contrib non-free
#deb-src http://deb.debian.org/debian bullseye-backports main contrib non-free

deb [signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bullseye stable
#deb-src [signed-by=/usr/share/keyrings/docker-archive-keyring.gpg]] https://download.docker.com/linux/debian bullseye stable

EOF
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

################################################################################
# Upgrade system
################################################################################
echo "" && cat /etc/debian_version && echo ""
apt-get update
apt-get upgrade -y --without-new-pkgs
apt-get -y full-upgrade
apt-get -y --purge autoremove
echo "" && cat /etc/debian_version && echo ""
