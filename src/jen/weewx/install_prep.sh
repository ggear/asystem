#!/bin/bash

chmod 666 /dev/ttyUSBVantagePro2
touch /home/weewx/bin/user/extensions.py
chown --reference=/home/weewx/bin/user/loopdata.py /home/weewx/bin/user/extensions.py
