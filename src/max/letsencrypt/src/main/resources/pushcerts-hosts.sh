#!/bin/bash

if ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "/var/lib/asystem/install/udmutilities/latest/image/udm-certificates/certificates.sh pull macmini-max udm-dar" &&
  ssh -n -q -o "StrictHostKeyChecking=no" root@udm-dar "/var/lib/asystem/install/udmutilities/latest/image/udm-certificates/certificates.sh push macmini-max udm-dar"; then
  logger -t pushcerts "Pushed new certificates to [udm-dar]"
else
  logger -t pushcerts "Failed to push new certificates to [udm-dar]"
fi
if ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "/var/lib/asystem/install/nginx/latest/data/certificates.sh pull macmini-max macmini-meg" &&
  ssh -n -q -o "StrictHostKeyChecking=no" root@macmini-meg "/var/lib/asystem/install/nginx/latest/data/certificates.sh push macmini-max macmini-meg"; then
  logger -t pushcerts "Pushed new certificates to [macmini-meg]"
else
  logger -t pushcerts "Failed to push new certificates to [macmini-meg]"
fi
