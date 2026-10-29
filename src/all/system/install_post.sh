#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

if [[ "${SERVICE_FORM_FACTOR:-}" == "server" ]]; then
  chmod +x "${SERVICE_INSTALL}/sleep.sh"
  ln -sfn "${SERVICE_INSTALL}/sleep.sh" /usr/local/bin/asleep
  install -m 755 "${SERVICE_INSTALL}/wake.sh" /usr/local/bin/awake
fi
