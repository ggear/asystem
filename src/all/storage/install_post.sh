#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

chmod +x "${SERVICE_INSTALL}/storage"
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
if [ -d /etc/bash_completion.d ]; then
  completion="$(mktemp)"
  "${SERVICE_INSTALL}/storage" completion >"${completion}" && install -m 644 "${completion}" /etc/bash_completion.d/storage
  rm -f "${completion}"
fi
