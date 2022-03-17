#!/bin/sh

[ ! -L /root/home ] && ln -s /home/asystem /root/home || true
[ ! -L /root/install ] && ln -s /var/lib/asystem/install /root/install || true
