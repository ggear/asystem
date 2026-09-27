#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

chmod +x "${SERVICE_INSTALL}/storage"
rm -f /usr/local/bin/astorage
cat >/usr/local/bin/astorage <<EOF
#!/bin/bash

${SERVICE_INSTALL}/storage "\$@"

EOF
chmod +x /usr/local/bin/astorage
rm -f /usr/local/bin/astorages
cat >/usr/local/bin/astorages <<EOF
#!/bin/bash

${SERVICE_INSTALL}/storage space --mode remote "\$@"

EOF
chmod +x /usr/local/bin/astorages
rm -f /usr/local/bin/amount
cat >/usr/local/bin/amount <<EOF
#!/bin/bash

${SERVICE_INSTALL}/storage mount "\$@"

EOF
chmod +x /usr/local/bin/amount
