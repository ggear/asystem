#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -p /data/media /data/backup/timemachine
cat <<EOF >/etc/samba/smb.conf
[global]
  workgroup = WORKGROUP
  log file = /var/log/samba/log.%m
  max log size = 1000
  logging = file
  panic action = /usr/share/samba/panic-action %d
  server role = standalone server
  obey pam restrictions = yes
  unix password sync = yes
  passwd program = /usr/bin/passwd %u
  passwd chat = *Enter\snew\s*\spassword:* %n\n *Retype\snew\s*\spassword:* %n\n *password\supdated\ssuccessfully* .
  pam password change = yes
  map to guest = bad user
  usershare allow guests = yes
  mdns name = mdns
  min protocol = SMB2
  vfs objects = fruit streams_xattr
  fruit:metadata = stream
  fruit:model = MacSamba
  fruit:posix_rename = yes
  fruit:veto_appledouble = no
  fruit:wipe_intentionally_left_blank_rfork = yes
  fruit:delete_empty_adfiles = yes
EOF
systemctl restart smbd
