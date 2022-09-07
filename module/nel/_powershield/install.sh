#!/bin/sh

. .env

################################################################################
# UPS
################################################################################
if [ $(grep "powershield" /etc/nut/ups.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/nut/ups.conf

[powershield]
driver = blazer_usb
port = auto

EOF
fi
if [ $(grep "0.0.0.0" /etc/nut/upsd.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/nut/upsd.conf

LISTEN 0.0.0.0 3493

EOF
fi
if [ $(grep "MODE=standalone" /etc/nut/nut.conf | wc -l) -eq 0 ]; then
  sed -i 's/MODE=none/MODE=standalone/g' /etc/nut/nut.conf
fi
if [ $(grep "${_UPS_KEY}" /etc/nut/upsd.users | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/nut/upsd.users

[upsmonitor]
password=${_UPS_KEY}
upsmon master

EOF
fi
if [ $(grep "${_UPS_KEY}" /etc/nut/upsmon.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/nut/upsmon.conf

MONITOR powershield@localhost 1 upsmonitor ${_UPS_KEY} master

EOF
fi
if [ $(grep "${_UPS_KEY}" /etc/nut/upssched.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/nut/upssched.conf

#CMDSCRIPT /bin/your-script.sh
#AT ONBATT * EXECUTE emailonbatt
#AT ONBATT * START-TIMER upsonbatt 300
#AT ONLINE * EXECUTE emailonline
#AT ONLINE * CANCEL-TIMER upsonbatt upsonline
#AT LOWBATT * EXECUTE low-batt
#AT SHUTDOWN * EXECUTE shutdown

EOF
fi
systemctl enable nut-driver.service
systemctl enable nut-server.service
systemctl enable nut-monitor.service
systemctl restart nut-driver.service
systemctl restart nut-server.service
systemctl restart nut-monitor.service
upsc powershield@localhost
