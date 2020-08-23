#!/bin/sh

set -x

################################################################################
# Todo
################################################################################
# Fix intermittent crashing, log uptime on 1.7.1-public.beta.1.2615
# Upgrade to a release quality version 1.7.2+
# Create nice to haves

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
# Clients -> udm-rack 192.168.1.1, macmini-liz 192.168.1.10, phillips-hue 192.168.1.12
# Routing & Firewall -> Port Forwarding -> Anode, 8091, 192.168.1.10, 8091, TCP, Enable Logging

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
