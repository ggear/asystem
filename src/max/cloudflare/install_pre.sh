#!/bin/bash

SYSCTL_CONF=/etc/sysctl.d/99-${SERVICE_NAME}.conf
SYSCTL_BUFFER_BYTES=7500000

cat >"${SYSCTL_CONF}" <<EOF
net.core.rmem_max=${SYSCTL_BUFFER_BYTES}
net.core.wmem_max=${SYSCTL_BUFFER_BYTES}
EOF

sysctl -p "${SYSCTL_CONF}"
