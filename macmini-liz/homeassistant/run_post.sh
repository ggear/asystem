#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

################################################################################
# Portal baseline
################################################################################
# Setup graham and jane users
# Integrations Core - HACS, Hue, Sonos, Google
# Integrations HACS - SenseMe
