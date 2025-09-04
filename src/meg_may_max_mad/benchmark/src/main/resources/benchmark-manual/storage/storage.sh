#!/bin/bash

lsblk -ro name,label
udevadm info /dev/sdb1
blkid /dev/sdb1
cd /tmp; umount -f /media/usbdrive 2>/dev/null; mount -t exfat /dev/sdb1 /media/usbdrive; cd /media/usbdrive;

iozone -i 0 -i 1 -s 1G -r 1M -e -I -R | grep ^\"1048576 | sed 's/"//g' | sed 's/1048576   /=/g' | sed 's/ /\/1000/g'
