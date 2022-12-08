#!/bin/sh

mkdir -p /var/lib/asystem
mkdir -p /mnt/data/asystem/install
if [[ ! -L /var/lib/asystem/install ]]; then
  if [[ -d /var/lib/asystem/install ]]; then
    cp -rvf /var/lib/asystem/install /mnt/data/asystem
    rm -rf /var/lib/asystem/install
  fi
  ln -s /mnt/data/asystem/install /var/lib/asystem/install
fi
