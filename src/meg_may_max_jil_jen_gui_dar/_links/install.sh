#!/bin/bash

mkdir -p /home/asystem
[ -d /root ] && [ ! -L /root/home ] && ln -s /home/asystem /root/home || true

mkdir -p /var/lib/asystem/install
[ -d /root ] && [ ! -L /root/install ] && ln -s /var/lib/asystem/install /root/install || true
