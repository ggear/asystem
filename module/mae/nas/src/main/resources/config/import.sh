#!/bin/bash

echo -n "Normalising /data ... "
setfacl -bR /data
chmod -R 644 /data
chmod -R a+rwX /data
chown -R nobody:nogroup /data
find /data -type f -name nohup -exec rm -f {} \;
find /data -type f -name .DS_Store -exec rm -f {} \;
echo "done"

import_files() {
  if [ -b /dev/sdc1 ] && [ -d /data/media/${1} ]; then
    mkdir -p /media/usbdrive
    umount -fq /media/usbdrive
    mount /dev/sdc1 /media/usbdrive
    if [ -d /media/usbdrive/${1} ]; then
      echo "Copying /media/usbdrive/${1} to /data/tmp/${1} ... "
      rsync -avP /media/usbdrive/${1} /data/tmp
      echo "Copy /media/usbdrive/${1} to /data/tmp/${1} complete"
      echo "Example renaming command: rename -v 's/(.*)S([0-9][0-9])E([0-9][0-9])\..*\.mkv/\$1s\$2e\$3.mkv/' *.mkv"
    fi
    umount -fq /media/usbdrive
  fi
}

import_files Audio
import_files Movies
import_files Series
