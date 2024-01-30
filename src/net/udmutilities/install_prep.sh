#!/bin/bash

mkdir -p /var/lib/asystem
mkdir -p /data/asystem/install
if [[ ! -L /var/lib/asystem/install ]]; then
  if [[ -d /var/lib/asystem/install ]]; then
    cp -rvf /var/lib/asystem/install /data/asystem
    rm -rf /var/lib/asystem/install
  fi
  ln -s /data/asystem/install /var/lib/asystem/install
fi

mkdir -p /home
mkdir -p /data/asystem/home/asystem
if [[ ! -L /home/asystem ]]; then
  if [[ -d /home/asystem ]]; then
    cp -rvf /home/asystem /data/asystem/home
    rm -rf /home/asystem
  fi
  ln -s /data/asystem/home/asystem /home/asystem
fi
rm -vrf /data/asystem/home/asystem/*
