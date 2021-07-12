#!/bin/sh

[ ! -L /root/home ] && ln -s /home/asystem /root/home
[ ! -L /root/install ] && ln -s /var/lib/asystem/install install
