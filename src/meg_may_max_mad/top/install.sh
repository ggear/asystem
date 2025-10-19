#!/bin/bash

chmod +x /var/lib/asystem/install/media/latest/bin/*.sh
for SCRIPT in /var/lib/asystem/install/media/latest/bin/*.sh; do
  rm -rf /usr/local/bin/asystem-$(basename "${SCRIPT}" .sh)
  ln -vs "${SCRIPT}" /usr/local/bin/asystem-$(basename "${SCRIPT}" .sh)
done
