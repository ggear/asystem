#!/bin/sh

cp -rvf /root/install/udmutilities/latest/config/udm-cloudflare-ddns/ddns-eth8-inadyn.conf /run/ddns-eth8-inadyn.conf
rm -rf /.inadyn
rm -rf /root/.inadyn
/usr/sbin/inadyn -n -s -C -f /run/ddns-eth8-inadyn.conf -1 -l debug --foreground
