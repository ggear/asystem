/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  telegraf --once >/dev/null 2>&1
