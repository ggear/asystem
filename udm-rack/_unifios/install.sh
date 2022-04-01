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
# Network -> Networks -> LAN -> Advanced -> Gateway IP/Subnet -> 10.0.0.1/24
# Network -> Networks -> LAN -> Advanced -> Auto Scale Network -> DHCP range -> 10.0.0.100 to 10.0.1.254

# Network -> Networks -> Add New Network -> Network Name -> Unfettered
# Network -> Networks -> Add New Network -> Advanced -> VLAN ID -> 2
# Network -> Networks -> Add New Network -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> Add New Network -> Advanced -> IGMP Snooping -> True
# Network -> Networks -> Add New Network -> Advanced -> Gateway IP/Subnet -> 10.0.2.1/24
# Network -> Networks -> Add New Network -> Advanced -> Auto Scale Network -> DHCP range -> 10.0.2.100 to 10.0.2.254
# Network -> Networks -> Add New Network -> Advanced -> DHCP UniFi OS Console -> 10.0.0.1

# Network -> Networks -> Add New Network -> Network Name -> Controlled
# Network -> Networks -> Add New Network -> Advanced -> VLAN ID -> 4
# Network -> Networks -> Add New Network -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> Add New Network -> Advanced -> IGMP Snooping -> True
# Network -> Networks -> Add New Network -> Advanced -> Gateway IP/Subnet -> 10.0.4.1/24
# Network -> Networks -> Add New Network -> Advanced -> Auto Scale Network -> DHCP range -> 10.0.4.100 to 10.0.4.254
# Network -> Networks -> Add New Network -> Advanced -> DHCP UniFi OS Console -> 10.0.0.1

# Network -> Networks -> Add New Network -> Network Name -> Isolated
# Network -> Networks -> Add New Network -> Advanced -> VLAN ID -> 6
# Network -> Networks -> Add New Network -> Advanced -> Domain Name -> janeandgraham.com
# Network -> Networks -> Add New Network -> Advanced -> IGMP Snooping -> True
# Network -> Networks -> Add New Network -> Advanced -> Gateway IP/Subnet -> 10.0.6.1/24
# Network -> Networks -> Add New Network -> Advanced -> Auto Scale Network -> DHCP range -> 10.0.6.100 to 10.0.6.254
# Network -> Networks -> Add New Network -> Advanced -> DHCP UniFi OS Console -> 10.0.0.1

# Network -> WiFi -> Add New WiFi Network -> Name/SSID -> MorkAndMindy
# Network -> WiFi -> Add New WiFi Network -> WPA Personal -> ${UNIFI_WIRELESS_MORK_AND_MINDY}
# Network -> WiFi -> Add New WiFi Network -> Network -> Unfettered
# Network -> WiFi -> Add New WiFi Network -> Advanced Options -> WiFi Band -> 2.4Ghz
# Network -> WiFi -> Add New WiFi Network -> Advanced Options -> Group Rekey Interval -> False
# Network -> WiFi -> Add New WiFi Network -> Rate and Beacon Controls -> 2G Data Rate Control -> True / 6 Mbps

# Network -> WiFi -> Add New WiFi Network -> Name/SSID -> BertAndErnie
# Network -> WiFi -> Add New WiFi Network -> WPA Personal -> ${UNIFI_WIRELESS_BERT_AND_ERNIE}
# Network -> WiFi -> Add New WiFi Network -> Network -> Controlled
# Network -> WiFi -> Add New WiFi Network -> Advanced Options -> WiFi Band -> 2.4Ghz
# Network -> WiFi -> Add New WiFi Network -> Advanced Options -> Group Rekey Interval -> False
# Network -> WiFi -> Add New WiFi Network -> Rate and Beacon Controls -> 2G Data Rate Control -> True / 6 Mbps

# Network -> WiFi -> Add New WiFi Network -> Name/SSID -> BeavisAndButthead
# Network -> WiFi -> Add New WiFi Network -> WPA Personal -> ${UNIFI_WIRELESS_BEAVIS_AND_BUTTHEAD}
# Network -> WiFi -> Add New WiFi Network -> Network -> Isolated
# Network -> WiFi -> Add New WiFi Network -> Advanced Options -> WiFi Band -> 2.4Ghz
# Network -> WiFi -> Add New WiFi Network -> Advanced Options -> Group Rekey Interval -> False
# Network -> WiFi -> Add New WiFi Network -> Rate and Beacon Controls -> 2G Data Rate Control -> True / 6 Mbps

# Advanced Features -> Switch Ports -> Add a Port Profile -> Broadcast
# Advanced Features -> Switch Ports -> Add a Port Profile -> Broadcast -> Native Network -> Unfettered
# Advanced Features -> Switch Ports -> Add a Port Profile -> Broadcast -> Tagged Networks -> Controlled, Isolated

# Devices -> Ports -> Assign Networks appropriately

# Traffic & Security -> Global Threat Management -> Detect & Block -> Detect & Block
# Traffic & Security -> System Sensitivity -> Maximum Protection

# Advanced Features -> Advanced Gateway Settings -> Create New Port Forwarding Rule ->
#    HTTP, Enabled, WAN, Any, 80, 10.0.2.12, 9080, TCP, Logging enable
#    HTTPS, Enabled, WAN, Any, 443, 10.0.2.12, 9443, TCP, Logging enable

mkdir -p /home
