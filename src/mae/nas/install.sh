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
fi
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
fi
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
fi
systemctl restart smbd
systemctl enable smbd
systemctl restart nmbd
systemctl enable nmbd
