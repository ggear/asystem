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
apt-get update && apt-get install -y curl gnupg-agent
cat <<EOF >/etc/apt/sources.list
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb http://deb.debian.org/debian-security/ bookworm-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware
deb http://deb.debian.org/debian bookworm-backports main contrib non-free non-free-firmware
deb [signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable
deb [signed-by=/usr/share/keyrings/coral-edgetpu.gpg] https://packages.cloud.google.com/apt coral-edgetpu-stable main
EOF
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --batch --yes --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --batch --yes --dearmor -o /usr/share/keyrings/coral-edgetpu.gpg

################################################################################
# Upgrade system
################################################################################
echo "" && cat /etc/debian_version && echo ""
apt-get update
apt-get upgrade -y --without-new-pkgs
apt-get -y full-upgrade
apt-get -y --purge autoremove
echo "" && cat /etc/debian_version && echo ""
