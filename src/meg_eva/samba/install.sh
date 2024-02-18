#!/bin/sh

################################################################################
# Samba
################################################################################
cat <<EOF >/etc/samba/smb.conf
[global]
  server min protocol = SMB2
  server max protocol = SMB3
  client min protocol = SMB2
  client max protocol = SMB3
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
for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  SHARE_INDEX=$(echo ${SHARE_DIR} | awk 'BEGIN{FS=OFS="/"}{print $3}')
  mkdir -p ${SHARE_DIR}/tmp
  mkdir -p ${SHARE_DIR}/media
  mkdir -p ${SHARE_DIR}/backup/media
  mkdir -p ${SHARE_DIR}/backup/service
  mkdir -p ${SHARE_DIR}/backup/timemachine
  rm -rf ${SHARE_DIR}/lost+found
  cat <<EOF >>/etc/samba/smb.conf
[share-${SHARE_INDEX}]
  comment = Share-${SHARE_INDEX} Files
  path = ${SHARE_DIR}
  public = yes
  browseable = yes
  read only = no
  writeable = yes
  force user = graham
  force group = users
  create mask = 0640
  directory mask = 0750
  force create mode = 0640
  force directory mode = 0750

EOF

  # TODO: Disable Time Machine share until we want it again
  #  cat <<EOF >>/etc/samba/smb.conf
  #[time-machine-${SHARE_INDEX}]
  #  comment = Time-Machine-${SHARE_INDEX} Files
  #  path = ${SHARE_DIR}/backup/timemachine
  #  public = yes
  #  browseable = yes
  #  read only = no
  #  writeable = yes
  #  force user = graham
  #  force group = users
  #  create mask = 0640
  #  directory mask = 0750
  #  force create mode = 0640
  #  force directory mode = 0750
  #  fruit:aapl = yes
  #  fruit:time machine = yes
  #  fruit:time machine max size = "4 T"
  #  vfs objects = fruit streams_xattr
  #
  #EOF

done
systemctl restart smbd
systemctl enable smbd
systemctl restart nmbd
systemctl enable nmbd

echo "" && echo "" && du -hd 0 /share/* && echo "" && echo ""
