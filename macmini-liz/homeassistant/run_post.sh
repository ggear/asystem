#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

################################################################################
# Portal baseline
################################################################################
# Setup graham and jane users
# Integrations - remove Meteorologisk, add Hue, Sonos, Google
# Integrations - autodiscover Hue, Sonos, Google
# Integrations - add HACS, BOM Forecast, BOM Weather Card, SenseMe,
#

cd "${SERVICE_INSTALL}" || exit
if [ $(docker exec -it homeassistant /bin/bash -c "[ ! -d /config/custom_components/hacs ]") ]; then
  docker exec -it homeassistant /bin/bash -c "curl -sfSL https://hacs.xyz/install | bash -"
  docker-compose --no-ansi up --force-recreate -d
fi
