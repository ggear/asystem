#!/bin/bash

################################################################################
# Upgrade system
################################################################################
echo "" && cat /etc/debian_version && echo ""
apt update
apt upgrade -y --without-new-pkgs
apt -y full-upgrade
apt -y --purge autoremove
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

deb [arch=amd64] http://download.docker.com/linux/debian bullseye stable
#deb-src [arch=amd64] http://download.docker.com/linux/debian bullseye stable

EOF

################################################################################
# Upgrade system
################################################################################
echo "" && cat /etc/debian_version && echo ""
apt update
apt upgrade -y --without-new-pkgs
apt -y full-upgrade
apt -y --purge autoremove
echo "" && cat /etc/debian_version && echo ""
