#!/bin/sh

[ -d "/var/lib/asystem/install" ] &&
  [ -d "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)" ] &&
  [ -f "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)/run.sh" ] &&
  cp -rvf "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)/run.sh" /mnt/data/on_boot.d/keys.sh
