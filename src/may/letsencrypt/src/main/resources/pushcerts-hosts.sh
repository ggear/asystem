#!/bin/bash

ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} pull macmini-may udm-dar \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} push macmini-may udm-dar \;"
logger -t pushcerts "Pushed new certificates to [udm-dar]"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} pull macmini-may macmini-meg \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} push macmini-may macmini-meg \;"
logger -t pushcerts "Pushed new certificates to [macmini-meg]"
ssh -n -q -o "StrictHostKeyChecking=no" root@macbook-rae "find /var/lib/asystem/install/appdaemon/latest/config -name certificates.sh -exec {} pull macmini-may macbook-rae \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@macbook-rae "find /var/lib/asystem/install/appdaemon/latest/config -name certificates.sh -exec {} push macmini-may macbook-rae \;"
logger -t pushcerts "Pushed new certificates to [macbook-rae]"
