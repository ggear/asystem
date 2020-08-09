#!/bin/sh

cp -rvf $(ls -td /var/lib/asystem/install/* | head -1)/udm-rack_*/host/run.sh /mnt/data/on_boot.d/keys.sh
