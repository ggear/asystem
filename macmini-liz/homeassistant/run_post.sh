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
if [ $(docker exec -it homeassistant /bin/bash -c "[ ! -d /config/www/icons/weather_icons ]") ]; then
  docker exec -it homeassistant /bin/bash -c "mkdir -p /config/www/icons/weather_icons && curl -o /tmp/icons.zip https://raw.githubusercontent.com/DavidFW1960/bom-weather-card/master/weather_icons.zip && unzip /tmp/icons.zip -d /config/www/icons/weather_icons && rm -rf /tmp/icons.zip"
  docker-compose --no-ansi up --force-recreate -d
fi

