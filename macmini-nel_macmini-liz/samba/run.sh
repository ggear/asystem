#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -vp /data/media /data/backup/timemachine /data/tmp
find /data -type f -name .DS_Store -exec rm -f {} \;
chmod -vR a+rwX /data
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

[Media]
  comment = Media Files
  path = /data/media
  browseable = yes
  read only = no
  guest ok = yes

[Time Machine]
  comment = Backup Files
  path = /data/backup/timemachine
  browseable = yes
  writable = yes
  read only = no
  guest ok = yes
  fruit:aapl = yes
  fruit:time machine = yes
  fruit:time machine max size = "4 T"
  vfs objects = fruit streams_xattr
EOF
systemctl restart smbd
systemctl enable smbd
