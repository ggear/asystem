#!/bin/sh

################################################################################
# Todo
################################################################################
# Fix intermittent crashing, log uptime on 1.7.1-public.beta.1.2615
# Upgrade to a release quality version 1.7.2+
# Add nice to haves

################################################################################
# Shell (unifi-os shell) baseline
################################################################################
# curl -L https://raw.githubusercontent.com/boostchicken/udm-utilities/master/on-boot-script/packages/udm-boot_1.0.1-1_all.deb -o udm-boot_1.0.1-1_all.deb
# dpkg -i udm-boot_1.0.1-1_all.deb

################################################################################
# Portal baseline
################################################################################
# Enable SSH

################################################################################
# Portal nice-to-have
################################################################################
# Add local alias graham with certificate

################################################################################
# Network baseline
################################################################################
# Wireless Networks -> BertAndErnie
# Networks -> LAN -> Domain name -> janeandgraham.com
# Networks -> LAN -> DHCP range -> 192.168.1.50 to 192.168.1.254
# Devices -> udm-rack, usw-house and uap-hallway
# Clients -> udm-rack 192.168.1.1, macbook-flo 192.168.1.9, macmini-liz 192.168.1.10, phillips-hue 192.168.1.12, lounge-tv 192.168.1.13, tplplug-* 192.168.1.20+, haiku-* 192.168.1.40+
# Routing & Firewall -> Port Forwarding -> Nginx, 80, 192.168.1.10, 9080, TCP, Enable Logging
# Routing & Firewall -> Port Forwarding -> Nginx, 443, 192.168.1.10, 9443, TCP, Enable Logging

################################################################################
# Network nice-to-have
################################################################################
# Clients -> names, icons
# Services -> Dynamic DNS -> Cloudflare version of (namecheap, home, janeandgraham.com, X, dynamicdns.park-your-domain.com)

################################################################################
# Protect baseline
################################################################################

################################################################################
# Protect nice-to-have
################################################################################
# Install and configure cameras

################################################################################
# Users
################################################################################
mkdir -p /home
