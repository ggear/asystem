#!/bin/bash
# https://ui.com/download/software/udm

################################################################################
# Device provision
################################################################################
# Name -> udm-dar
# Devices -> Adopt all
# Wireless -> Create BertAndErnie/$UNIFI_WIRELESS_BERT_AND_ERNIE

################################################################################
# OS baseline
################################################################################
# Login via http://unifi.ui.com or http://192.168.1.1

# Applications -> Auto Update -> UniFi OS -> False
# Applications -> Auto Update -> Applications -> False
# Applications -> Install/Update Network/Protect/InnerSpace

# Admins & Users -> Admins -> Add -> unifi/$UNIFI_ADMIN_KEY, Local Access Only, Super Admin
# Admins & Users -> Admins -> Add -> protect/$UNIFI_PROTECT_KEY, Local Access Only, Super Admin
# Admins & Users -> Admins -> Add -> monitor/$UNFI_MONITOR_KEY, Local Access Only, Super Admin
# Admins & Users -> Admins -> Add -> graham/$UNFI_GRAHAM_KEY, Local Access Only, Super Admin
# Admins & Users -> Admins -> Add -> jane/$UNFI_JANE_KEY, Local Access Only, Super Admin

# Console Settings -> Advanced -> Remote Access -> False (Only available with the graham account.ui.com account)
# Console Settings -> Advanced -> SSH -> True, $UNIFI_ROOT_KEY (to get past password restrictions, then reset to standard with passwd), graham/$UNIFI_DEVICE_KEY and Graham/~/.ssh/id_rsa.pub

################################################################################
# Network baseline
################################################################################
# Devices -> Rename as per entity_metadata.xlsx
# Devices -> uap-deck -> Settings -> LED -> False
# Devices -> uap-deck -> Settings -> 2.4GHz Channel -> 11 (Potentially use 3 8 13 to squeeze a third around Zigbee 11?)
# Devices -> uap-deck -> Settings -> 2.4GHz Transmit Power -> High
# Devices -> uap-deck -> Settings -> 5GHz Channel -> 48
# Devices -> uap-deck -> Settings -> 5GHz Transmit Power -> High
# Devices -> uap-hallway -> Settings -> LED -> False
# Devices -> uap-hallway -> Settings -> 2.4GHz Channel -> 6 (Potentially use 3 8 13 to squeeze a third around Zigbee 11?)
# Devices -> uap-hallway -> Settings -> 2.4GHz Transmit Power -> High
# Devices -> uap-hallway -> Settings -> 5GHz Channel -> 36
# Devices -> uap-hallway -> Settings -> 5GHz Transmit Power -> High

# Settings -> System -> Backups -> Auto Backup -> False
# Settings -> System -> Updates -> Automate Device Updates -> False
# Settings -> System -> Advanced -> Email Services -> False
# Settings -> System -> Advanced -> Wireless Connectivity -> Wireless Meshing -> False
# Settings -> System -> Advanced -> Device Authentication -> Keys

# Settings -> Networks -> IPv6 Support -> False
# Settings -> Networks -> IGMP Snooping -> False
# Settings -> Networks -> IGMP Proxy -> False

# Settings -> Networks -> Default -> Network Name -> Default
# Settings -> Networks -> Default -> Gateway IP/Subnet -> Auto-Scale Network -> False
# Settings -> Networks -> Default -> Gateway IP/Subnet -> 10.0.1.1/24
# Settings -> Networks -> Default -> Advanced -> Manual
# Settings -> Networks -> Default -> IGMP Snooping -> False
# Settings -> Networks -> Default -> Multicast DNS -> True
# Settings -> Networks -> Default -> DHCP Range -> 10.0.1.150/10.0.1.254
# Settings -> Networks -> Default -> Domain Name -> local.janeandgraham.com

# Settings -> Networks -> New Virtual Network -> Network Name -> Unfettered
# Settings -> Networks -> New Virtual Network -> Gateway IP/Subnet -> Auto-Scale Network -> False
# Settings -> Networks -> New Virtual Network -> Gateway IP/Subnet -> 10.0.2.1/24
# Settings -> Networks -> New Virtual Network -> Advanced -> Manual
# Settings -> Networks -> New Virtual Network -> VLAN ID -> 2
# Settings -> Networks -> New Virtual Network -> IGMP Snooping -> False
# Settings -> Networks -> New Virtual Network -> Multicast DNS -> True
# Settings -> Networks -> New Virtual Network -> DHCP Range -> 10.0.2.150/10.0.2.254
# Settings -> Networks -> New Virtual Network -> Domain Name -> local.janeandgraham.com

# Settings -> Networks -> New Virtual Network -> Network Name -> Controlled
# Settings -> Networks -> New Virtual Network -> Gateway IP/Subnet -> Auto-Scale Network -> False
# Settings -> Networks -> New Virtual Network -> Gateway IP/Subnet -> 10.0.3.1/24
# Settings -> Networks -> New Virtual Network -> Advanced -> Manual
# Settings -> Networks -> New Virtual Network -> VLAN ID -> 3
# Settings -> Networks -> New Virtual Network -> IGMP Snooping -> False
# Settings -> Networks -> New Virtual Network -> Multicast DNS -> True
# Settings -> Networks -> New Virtual Network -> DHCP Range -> 10.0.3.150/10.0.3.254
# Settings -> Networks -> New Virtual Network -> Domain Name -> local.janeandgraham.com

# Settings -> Networks -> New Virtual Network -> Network Name -> Isolated
# Settings -> Networks -> New Virtual Network -> Gateway IP/Subnet -> Auto-Scale Network -> False
# Settings -> Networks -> New Virtual Network -> Gateway IP/Subnet -> 10.0.4.1/24
# Settings -> Networks -> New Virtual Network -> Advanced -> Manual
# Settings -> Networks -> New Virtual Network -> VLAN ID -> 4
# Settings -> Networks -> New Virtual Network -> IGMP Snooping -> False
# Settings -> Networks -> New Virtual Network -> Multicast DNS -> True
# Settings -> Networks -> New Virtual Network -> DHCP Range -> 10.0.4.150/10.0.4.254
# Settings -> Networks -> New Virtual Network -> DHCP Guarding -> True / 10.0.4.1
# Settings -> Networks -> New Virtual Network -> Domain Name -> local.janeandgraham.com

# Settings -> WiFi -> BertAndErnie -> Network -> Controlled
# Settings -> WiFi -> BertAndErnie -> WiFi Band -> 2.4Ghz / 5Ghz
# Settings -> WiFi -> BertAndErnie -> Band Steering -> True
# Settings -> WiFi -> BertAndErnie -> BSS Transition -> True
# Settings -> WiFi -> BertAndErnie -> Multicast Enhancement -> True

# Settings -> WiFi -> Create New -> Name -> MorkAndMindy
# Settings -> WiFi -> Create New -> WPA Personal -> ${UNIFI_WIRELESS_MORK_AND_MINDY}
# Settings -> WiFi -> Create New -> Network -> Unfettered
# Settings -> WiFi -> Create New -> WiFi Band -> 2.4Ghz
# Settings -> WiFi -> Create New -> BSS Transition -> True
# Settings -> WiFi -> Create New -> Multicast Enhancement -> True

# Settings -> WiFi -> Create New -> Name -> BeavisAndButthead
# Settings -> WiFi -> Create New -> WPA Personal -> ${UNIFI_WIRELESS_BEAVIS_AND_BUTTHEAD}
# Settings -> WiFi -> Create New -> Network -> Isolated
# Settings -> WiFi -> Create New -> WiFi Band -> 2.4Ghz
# Settings -> WiFi -> Create New -> BSS Transition -> True
# Settings -> WiFi -> Create New -> Multicast Enhancement -> True

# Ports -> Network device ports to be left as Default, Allow All
# Ports -> Server and unused ports to be assigned Unfettered, Allow All
# Ports -> Cameras and printer ports to be assigned Isolated, Block All

# Settings -> Security -> Port Forwarding -> Name -> HTTP
# Settings -> Security -> Port Forwarding -> From -> Any
# Settings -> Security -> Port Forwarding -> Port -> 80
# Settings -> Security -> Port Forwarding -> Forward IP -> 10.0.2.21
# Settings -> Security -> Port Forwarding -> Forward Port -> 80
# Settings -> Security -> Port Forwarding -> Protocol -> TCP
# Settings -> Security -> Port Forwarding -> Logging -> True

# Settings -> Security -> Port Forwarding -> Name -> HTTPS
# Settings -> Security -> Port Forwarding -> From -> Any
# Settings -> Security -> Port Forwarding -> Port -> 443
# Settings -> Security -> Port Forwarding -> Forward IP -> 10.0.2.21
# Settings -> Security -> Port Forwarding -> Forward Port -> 443
# Settings -> Security -> Port Forwarding -> Protocol -> TCP
# Settings -> Security -> Port Forwarding -> Logging -> True

# Settings -> Security -> Port Forwarding -> Name -> BitTorrent
# Settings -> Security -> Port Forwarding -> From -> Any
# Settings -> Security -> Port Forwarding -> Port -> 58671
# Settings -> Security -> Port Forwarding -> Forward IP -> 10.0.2.21
# Settings -> Security -> Port Forwarding -> Forward Port -> 51413
# Settings -> Security -> Port Forwarding -> Protocol -> Both
# Settings -> Security -> Port Forwarding -> Logging -> True

# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> Static IP -> True
# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> IPv4 Address -> 123.176.113.184
# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> Subnet Mask -> 255.255.255.0
# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> Gateway IP -> 123.176.113.1
# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> Additional IP Addresses -> 10.0.0.1/24
# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> DNS Auto -> False
# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> Primary Server -> 1.1.1.1
# Settings -> Internet -> Primary (WAN1) -> IPv4 Connection -> Secondary Server -> 1.0.0.1

################################################################################
# Not done
################################################################################
# Name UniFi and User devices

# Traffic & Security -> Global Threat Management -> Detect & Block -> Detect & Block
# Traffic & Security -> System Sensitivity -> Maximum Protection
# Traffic & Security -> Create New Rule -> Enable Rule -> True, Description -> Isolated from Internet, Action -> Block, Matching -> Internet, On -> Isolated

# Advanced Features -> Advanced Gateway Settings -> Multicast DNS -> True

# Protect setup cameras, medium streaming

# Wireless coverage floorplan setup

# Classic UI -> Site -> Auto-optimize network -> False
# Classic UI -> All Wireless Networks -> Block LAN to WLAN multicast and broadcast data -> False
