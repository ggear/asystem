#!/bin/bash

chmod +x /var/lib/asystem/install/top/latest/bin/*.sh
for SCRIPT in /var/lib/asystem/install/top/latest/bin/*.sh; do
  rm -rf /usr/local/bin/$(basename "${SCRIPT}" .sh)
  ln -vs "${SCRIPT}" /usr/local/bin/$(basename "${SCRIPT}" .sh)
done
