#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

chmod +x "${SERVICE_INSTALL}/storage"
rm -f /usr/local/bin/astorage /usr/local/bin/astorages /usr/local/bin/aspaces
rm -f /usr/local/bin/aspace
cat >/usr/local/bin/aspace <<EOF
#!/bin/bash

${SERVICE_INSTALL}/storage space "\$@"

EOF
chmod +x /usr/local/bin/aspace
rm -f /usr/local/bin/amount
cat >/usr/local/bin/amount <<EOF
#!/bin/bash

${SERVICE_INSTALL}/storage mount "\$@"

EOF
chmod +x /usr/local/bin/amount
