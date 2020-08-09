#!/bin/sh

[ -d "/var/lib/asystem/install" ] &&
  [ -d "$(ls -td /var/lib/asystem/install/* | head -1)" ] &&
  [ -f "$(ls -td /var/lib/asystem/install/* | head -1)/udm-rack_*/host/run.sh" ] &&
  cp -rvf "$(ls -td /var/lib/asystem/install/* | head -1)/udm-rack_*/host/run.sh" /mnt/data/on_boot.d/keys.sh
