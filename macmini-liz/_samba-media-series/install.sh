#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -vp /data/media/Series
if [ $(grep "/data/media/Series" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Series]
  comment = Media Files
  path = /data/media/Series
  browseable = yes
  read only = no
  guest ok = yes

EOF
  systemctl restart smbd
  systemctl enable smbd
fi
