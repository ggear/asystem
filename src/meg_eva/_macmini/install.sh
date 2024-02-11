#!/bin/bash

################################################################################
# Packages
################################################################################
apt-get update
apt-get install -y --allow-downgrades 'intel-microcode=3.20231114.1~deb12u1'
apt-get install -y --allow-downgrades 'libc6-i386=2.36-9+deb12u4'

################################################################################
# Intel network card
################################################################################
if [ -f /etc/default/grub ] && [ $(grep "intel_iommu=on iommu=pt" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="quiet/GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt/' /etc/default/grub
  update-grub
fi
