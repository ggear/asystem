#!/bin/sh

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
# Updates -> UDM Pro / Apps -> Off
# Location / Time -> Set
# Advanced -> SSH
# Users ->
#   Super Admin, Local Access Only, Unifi Admin, unifi
#   Limited Admin, Local Access Only, Unifi Protect, protect
#   Limited Admin, Local Access Only, Unifi Protect, protect
#   Limited Admin, Ubiquiti Account, jane.m.thomson@gmail.com
# Network -> WiFi -> BertAndErnie
# Network -> Networks -> LAN -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> LAN -> Advanced -> Auto Scale Network -> DHCP range -> 192.168.1.100 to 192.168.1.254
# Network -> Devices -> udm-rack, usw-ceiling, uap-deck, uap-hallway, uvc-ada, uvc-edwin
# Traffic & Security -> Global Threat Management -> Detect & Block -> Detect & Block
# Traffic & Security -> System Sensitivity -> Maximum Protection
# Advanced Features -> Advanced Gateway Settings -> Create New Port Forwarding Rule ->
#    HTTP, Enabled, WAN, Any, 80, 192.168.1.3, 9080, TCP, Logging enable
#    HTTPS, Enabled, WAN, Any, 443, 192.168.1.3, 9443, TCP, Logging enable
# Network -> Clients ->
#   udm-rack 192.168.1.1
#   macbook-flo 192.168.1.2
#   macmini-liz 192.168.1.3
#   macmini-nel 192.168.1.4
#   appletv-lounge 192.168.1.10
#   phillips-hue 192.168.1.11
#   uvc-ada 192.168.1.15
#   uvc-edwin 192.168.1.16
#   haiku-* 192.168.1.30-39
#   tplplug-* 192.168.1.40-59
#   brother-printer 192.168.1.12

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
