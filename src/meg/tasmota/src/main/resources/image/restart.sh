#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

ENV_DIR="$ROOT_DIR"
while [ "$ENV_DIR" != "/" ] && [ ! -f "$ENV_DIR/.env" ]; do ENV_DIR="$(dirname "$ENV_DIR")"; done
# shellcheck disable=SC1091
[ -f "$ENV_DIR/.env" ] && . "$ENV_DIR/.env"

BROKER_ARGS=(-h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT")

DEVICES=(
  ceiling_network_switch_plug
  ceiling_water_booster_plug
  deck_festoons_plug
  garden_pool_filter_plug
  kitchen_bench_lights_plug
  kitchen_fan_plug
  landing_festoons_plug
  rack_backup_plug
  rack_fans_plug
  rack_outlet_plug
  rack_printer_plug
  rack_screen_plug
)

printf '\nDevice restart script [tasmota] restarting [%d] devices on [%s], each republishing its retained state on boot:\n' "${#DEVICES[@]}" "$VERNEMQ_SERVICE"
for DEVICE in "${DEVICES[@]}"; do
  printf '%s\n' "$DEVICE"
  mosquitto_pub "${BROKER_ARGS[@]}" -t "tasmota/device/${DEVICE}/cmnd/Restart" -m "1"
done

printf '\nDevice restart script [tasmota] waiting for devices to boot ... ' && sleep 30 && printf 'done\n'

RESTARTED=$(mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t 'tasmota/device/+/tele/LWT' -W 5 2>/dev/null | sort -u | wc -l | tr -d ' ')
printf '\nDevice restart script [tasmota] restarted [%s] of [%d] devices\n\n' "$RESTARTED" "${#DEVICES[@]}"
[ "$RESTARTED" -ge "${#DEVICES[@]}" ]
