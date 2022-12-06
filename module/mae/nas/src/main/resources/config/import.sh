#!/bin/bash

echo "" && echo "ssh root@$(hostname)" && echo -n "Normalising /data ... "
setfacl -bR /data
chmod -R 644 /data
chmod -R a+rwX /data
chown -R nobody:nogroup /data
find /data -type f -name nohup -exec rm -f {} \;
find /data -type f -name .DS_Store -exec rm -f {} \;
echo "done" && echo ""

import_files() {
  if [ -b /dev/sdc1 ] && [ -d /data/media/${1} ]; then
    mkdir -p /media/usbdrive
    umount -fq /media/usbdrive
    mount /dev/sdc1 /media/usbdrive
    if [ -d /media/usbdrive/${1} ]; then
      rsync -avP /media/usbdrive/${1} /data/tmp
    fi
    umount -fq /media/usbdrive
    echo "" && echo "ssh root@$(hostname)" && echo "rename -v 's/(.*)S([0-9][0-9])E([0-9][0-9])\..*\.mkv/\$1s\$2e\$3.mkv/' *.mkv" && echo ""
  fi
}

import_files Audio
import_files Movies
import_files Series
