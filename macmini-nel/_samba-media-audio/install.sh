#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -vp /data/media/Audio
if [ $(grep "/data/media/Audio" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Audio]
  comment = Media Files
  path = /data/media/Audio
  browseable = yes
  read only = no
  guest ok = yes

EOF
  systemctl restart smbd
  systemctl enable smbd
fi
