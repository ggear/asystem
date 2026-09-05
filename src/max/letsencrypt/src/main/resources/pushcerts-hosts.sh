#!/bin/bash

ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} pull macmini-max udm-dar \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} push macmini-max udm-dar \;"
logger -t pushcerts "Pushed new certificates to [udm-dar]"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} pull macmini-max macmini-meg \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} push macmini-max macmini-meg \;"
logger -t pushcerts "Pushed new certificates to [macmini-meg]"
