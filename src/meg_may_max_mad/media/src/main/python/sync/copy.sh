#!/bin/bash

parted /dev/sdb --script mklabel gpt
parted /dev/sdb set 1 msftdata on
parted -a optimal /dev/sdb --script mkpart primary 0% 100%
mkfs.exfat -n DATA /dev/sdb1
