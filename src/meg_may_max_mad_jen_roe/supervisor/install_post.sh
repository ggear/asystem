#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

. "${SERVICE_INSTALL}/.env"

chmod +x "${SERVICE_INSTALL}/data/supervisor"
cat >/usr/local/bin/atop <<"EOF"
#!/bin/bash

${SERVICE_INSTALL}/data/supervisor watch -m local -F 1 "$@"

EOF
chmod +x /usr/local/bin/atop
cat >/usr/local/bin/atops <<"EOF"
#!/bin/bash

${SERVICE_INSTALL}/data/supervisor watch -m remote "$@"

EOF
chmod +x /usr/local/bin/atops
