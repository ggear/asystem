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

mkdir -p /home
mkdir -p /mnt/data/asystem/home/asystem
if [[ ! -L /home/asystem ]]; then
  if [[ -d /home/asystem ]]; then
    cp -rvf /home/asystem /mnt/data/asystem/home
    rm -rf /home/asystem
  fi
  ln -s /mnt/data/asystem/home/asystem /home/asystem
fi
