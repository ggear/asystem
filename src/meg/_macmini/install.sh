#!/bin/sh

################################################################################
# Intel network card
################################################################################
if [ -f /etc/default/grub ] && [ $(grep "intel_iommu=on iommu=pt" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="quiet/GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt/' /etc/default/grub
  update-grub
fi