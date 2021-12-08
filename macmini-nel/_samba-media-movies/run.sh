#!/bin/sh

################################################################################
# Samba
################################################################################
mkdir -vp /data/media/Movies
if [ $(grep "/data/media/Movies" /etc/samba/smb.conf | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/samba/smb.conf
[Media Movies]
  comment = Media Files
  path = /data/media/Movies
  browseable = yes
  read only = no
  guest ok = yes

EOF
  systemctl restart smbd
  systemctl enable smbd
fi
