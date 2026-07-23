#!/bin/bash

docker exec weewx sh -c 'touch /home/weewx/bin/user/extensions.py && chown --reference=/home/weewx/bin/user/loopdata.py /home/weewx/bin/user/extensions.py'
