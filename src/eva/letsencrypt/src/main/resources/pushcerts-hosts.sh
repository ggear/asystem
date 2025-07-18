#!/bin/bash

ssh -n -q -o "StrictHostKeyChecking=no" root@udm-net "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} pull macmini-eva udm-net \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@udm-net "find /var/lib/asystem/install/udmutilities/latest/config -name certificates.sh -exec {} push macmini-eva udm-net \;"
logger -t pushcerts "Pushed new certificates to [udm-net]"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} pull macmini-eva macmini-meg \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "find /var/lib/asystem/install/nginx/latest/config -name certificates.sh -exec {} push macmini-eva macmini-meg \;"
logger -t pushcerts "Pushed new certificates to [macmini-meg]"
ssh -n -q -o "StrictHostKeyChecking=no" root@macbook-rae "find /var/lib/asystem/install/appdaemon/latest/config -name certificates.sh -exec {} pull macmini-eva macbook-rae \;"
ssh -n -q -o "StrictHostKeyChecking=no" root@macbook-rae "find /var/lib/asystem/install/appdaemon/latest/config -name certificates.sh -exec {} push macmini-eva macbook-rae \;"
logger -t pushcerts "Pushed new certificates to [macbook-rae]"
