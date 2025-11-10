/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  influxdb3 show license info --format json | jq -e '.[0].expires_at as $e | (now < (($e + "Z") | fromdateiso8601))' >/dev/null
