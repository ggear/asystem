#!/bin/bash

set -Eeuo pipefail

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
NUT_CONF_DIR="${NUT_CONF_DIR:-/etc/ups}"

# shellcheck disable=SC1090
. "${ENV_FILE}"

[[ "${SERVICE_FORM_FACTOR:-}" == "server" && "${SERVICE_COMMAND:-}" == "install" ]] || exit 0

UPS_NAME="$(basename "${RACKMAINS_DEVICE:-}")"
if [[ "${UPS_NAME}" != nutdrv_qx-?* ]]; then
  echo "Left [${NUT_CONF_DIR}] alone, device [${RACKMAINS_DEVICE:-}] is not a socket named nutdrv_qx-ups" >&2
  exit 0
fi
UPS_NAME="${UPS_NAME#nutdrv_qx-}"

if ! rpm -q nut nut-client >/dev/null 2>&1 && ! dnf install -y nut nut-client; then
  echo "Left [${NUT_CONF_DIR}] alone, could not install [nut nut-client]" >&2
  exit 0
fi

CHANGED=false

put() {
  local file="${NUT_CONF_DIR}/$1" content
  content="$(cat)"
  if [[ "$(cat "${file}" 2>/dev/null)" != "${content}" ]]; then
    printf '%s\n' "${content}" >"${file}"
    echo "Updated [${file}]"
    CHANGED=true
  fi
  chmod 640 "${file}"
  chown root:nut "${file}"
}

put nut.conf <<EOT
MODE=standalone
EOT

put ups.conf <<EOT
maxretry = 3

[${UPS_NAME}]
    driver = nutdrv_qx
    port = auto
    vendorid = 0665
    productid = 5161
    protocol = voltronic-qs
    pollfreq = 4
    desc = "PowerShield UPS"
EOT

put upsd.conf <<EOT
LISTEN 127.0.0.1 3493
EOT

UNITS=("nut-driver@${UPS_NAME}.service" nut-server.service)
systemctl enable --now "${UNITS[@]}" || echo "Could not enable [${UNITS[*]}]" >&2
if [[ "${CHANGED}" == "true" ]]; then
  systemctl restart "${UNITS[@]}" || echo "Could not restart [${UNITS[*]}]" >&2
fi
