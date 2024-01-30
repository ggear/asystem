#!/bin/bash

cp -uvf /root/install/udmutilities/latest/config/udm-certificates/.key.pem /data/unifi-core/config/unifi-core.key
cp -uvf /root/install/udmutilities/latest/config/udm-certificates/certificate.pem /data/unifi-core/config/unifi-core.crt

echo "Installed latest certificates ..."
