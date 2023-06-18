#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -vp /data/backup/timemachine
if [ $(grep "/data/backup/timemachine" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
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
fi
systemctl restart smbd
systemctl enable smbd
systemctl restart nmbd
systemctl enable nmbd
