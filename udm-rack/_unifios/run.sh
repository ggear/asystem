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


# Network -> Networks -> LAN -> Network Name -> Management
# Network -> Networks -> LAN -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> LAN -> Advanced -> IGMP Snooping -> True
# Network -> Networks -> LAN -> Advanced -> Gateway IP/Subnet -> 192.168.1.1/24
# Network -> Networks -> LAN -> Advanced -> Auto Scale Network -> DHCP range -> 192.168.1.150 to 192.168.1.254

# Network -> Networks -> Unfettered -> Network Name -> Unfettered
# Network -> Networks -> Unfettered -> Advanced -> VLAN ID -> 3
# Network -> Networks -> Unfettered -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> Unfettered -> Advanced -> IGMP Snooping -> True
# Network -> Networks -> Unfettered -> Advanced -> Gateway IP/Subnet -> 192.168.3.1/24
# Network -> Networks -> Unfettered -> Advanced -> Auto Scale Network -> DHCP range -> 192.168.3.150 to 192.168.3.254
# Network -> Networks -> Unfettered -> Advanced -> DHCP UniFi OS Console -> 192.168.1.1

# Network -> Networks -> Controlled -> Network Name -> Controlled
# Network -> Networks -> Controlled -> Advanced -> VLAN ID -> 5
# Network -> Networks -> Controlled -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> Controlled -> Advanced -> IGMP Snooping -> True
# Network -> Networks -> Controlled -> Advanced -> Gateway IP/Subnet -> 192.168.5.1/24
# Network -> Networks -> Controlled -> Advanced -> Auto Scale Network -> DHCP range -> 192.168.5.150 to 192.168.5.254
# Network -> Networks -> Controlled -> Advanced -> DHCP UniFi OS Console -> 192.168.1.1

# Network -> Networks -> Isolated -> Network Name -> Isolated
# Network -> Networks -> Isolated -> Advanced -> VLAN ID -> 7
# Network -> Networks -> Isolated -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> Isolated -> Advanced -> IGMP Snooping -> True
# Network -> Networks -> Isolated -> Advanced -> Gateway IP/Subnet -> 192.168.7.1/24
# Network -> Networks -> Isolated -> Advanced -> Auto Scale Network -> DHCP range -> 192.168.7.150 to 192.168.7.254
# Network -> Networks -> Isolated -> Advanced -> DHCP UniFi OS Console -> 192.168.1.1



# Network -> WiFi -> BertAndErnie ->




# Network -> Devices -> udm-rack, usw-ceiling, uap-deck, uap-hallway, uvc-ada, uvc-edwin
# Traffic & Security -> Global Threat Management -> Detect & Block -> Detect & Block
# Traffic & Security -> System Sensitivity -> Maximum Protection
# Traffic & Security -> Create New Rule -> Block TPLink, Block, Internet, 18 x tplplug-*
# Advanced Features -> Advanced Gateway Settings -> Create New Port Forwarding Rule ->
#    HTTP, Enabled, WAN, Any, 80, 192.168.1.3, 9080, TCP, Logging enable
#    HTTPS, Enabled, WAN, Any, 443, 192.168.1.3, 9443, TCP, Logging enable





# Network -> Clients ->
#   udm-rack 192.168.1.1
#   macbook-flo 192.168.1.2
#   macmini-liz 192.168.1.3
#   macmini-nel 192.168.1.4
#   phillips-hue 192.168.1.11
#   brother-printer 192.168.1.12
#   uvc-ada 192.168.1.15
#   uvc-edwin 192.168.1.16
#   haiku-* 192.168.1.30-39
#   tplplug-* 192.168.1.40-59

#   pihole - 192.168.1.2
#   start servers at 10
#   sonoffpowr3-* (5x) - statically define?
#   nestmini-* (6x) - statically define?
#   chromecast-parents 192.168.1.8 - re-define?
#   homepod-lounge 192.168.1.9 - re-define?
#   appletv-lounge 192.168.1.10 - re-define?
#   sonos* (5x) - statically define?
#   netatmo* (10x) - statically define?

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
