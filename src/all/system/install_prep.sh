#!/bin/bash

set -Eeuo pipefail

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env"

[[ "${SERVICE_FORM_FACTOR:-}" == "server" && "${SERVICE_COMMAND:-}" == "install" ]] || exit 0

################################################################################
# Power loss restart
################################################################################
if [[ "$(uname -m)" == "x86_64" && "$(cat /sys/class/dmi/id/product_name 2>/dev/null)" == Macmini* ]] && command -v setpci >/dev/null; then
  LPC=00:1f.0
  if [[ "$(setpci -s ${LPC} 0x00.w)" == "8086" && "$(setpci -s ${LPC} 0x0a.w)" == "0601" ]]; then
    GEN_PMCON_3=$((16#$(setpci -s ${LPC} 0xa4.w)))
    if ((GEN_PMCON_3 & 1)); then
      setpci -s ${LPC} "0xa4.w=$(printf '%04x' $((GEN_PMCON_3 & ~1)))" || echo "Failed to set AFTERG3_EN on [${LPC}]" >&2
    fi
    GEN_PMCON_3="$(setpci -s ${LPC} 0xa4.w)"
    echo "Power loss restart, GEN_PMCON_3 [${GEN_PMCON_3}] AFTERG3_EN [$((16#${GEN_PMCON_3} & 1))] (0 restarts)"
  fi
elif [[ "$(uname -m)" == "aarch64" ]]; then
  AC_POWER_MODE=/sys/bus/platform/devices/macsmc-reboot/ac_power_mode
  if [[ -w "${AC_POWER_MODE}" ]]; then
    echo restore >"${AC_POWER_MODE}" || echo "Failed to set [${AC_POWER_MODE}]" >&2
  else
    echo "No [${AC_POWER_MODE}] on kernel [$(uname -r)], power loss restart must be set in macOS" >&2
  fi
fi
