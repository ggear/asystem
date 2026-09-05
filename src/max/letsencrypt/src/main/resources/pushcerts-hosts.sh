#!/bin/bash

ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} pull macmini-max udm-dar \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} push macmini-max udm-dar \;"
logger -t pushcerts "Pushed new certificates to [udm-dar]"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} pull macmini-max macmini-meg \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} push macmini-max macmini-meg \;"
logger -t pushcerts "Pushed new certificates to [macmini-meg]"
ssh -n -q -o "StrictHostKeyChecking=no" root@nullsvr-zzz "find /var/lib/asystem/install/appdaemon/latest/config -name certificates.sh -exec {} pull macmini-max nullsvr-zzz \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@nullsvr-zzz "find /var/lib/asystem/install/appdaemon/latest/config -name certificates.sh -exec {} push macmini-max nullsvr-zzz \;"
logger -t pushcerts "Pushed new certificates to [nullsvr-zzz]"
