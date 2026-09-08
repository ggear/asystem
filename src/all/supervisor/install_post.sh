#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

# shellcheck disable=SC1091
. "${SERVICE_INSTALL}/.env"

chmod +x "${SERVICE_INSTALL}/supervisor"
cat >/usr/local/bin/atop <<EOF
#!/bin/bash

${SERVICE_INSTALL}/supervisor watch -m local -F 1 "\$@"

EOF
chmod +x /usr/local/bin/atop
cat >/usr/local/bin/atops <<EOF
#!/bin/bash

${SERVICE_INSTALL}/supervisor watch -m remote "\$@"

EOF
chmod +x /usr/local/bin/atops
