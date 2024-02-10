#!/bin/sh

################################################################################
# Samba
################################################################################
if [ $(grep "fruit" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >/etc/samba/smb.conf
[global]
  min protocol = SMB2
  server role = standalone server
  workgroup = WORKGROUP
  log file = /var/log/samba/log.%m
  logging = file
  max log size = 1000
  load printers = no
  access based share enum = no
  hide unreadable = no
  panic action = /usr/share/samba/panic-action %d
  obey pam restrictions = yes
  unix password sync = yes
  passwd program = /usr/bin/passwd %u
  passwd chat = *Enter\snew\s*\spassword:* %n\n *Retype\snew\s*\spassword:* %n\n *password\supdated\ssuccessfully* .
  pam password change = yes
  map to guest = bad user
  usershare allow guests = yes
  mdns name = mdns
  vfs objects = fruit streams_xattr
  fruit:delete_empty_adfiles = yes
  fruit:metadata = stream
  fruit:model = TimeCapsule9,119
  fruit:posix_rename = yes
  fruit:veto_appledouble = no
  fruit:wipe_intentionally_left_blank_rfork = yes
EOF
fi
systemctl restart smbd
systemctl enable smbd
systemctl restart nmbd
systemctl enable nmbd
