/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  ! grep -Eq '^10\.0\.[0-9]+\.[0-9]+:' /config/ip_bans.yaml 2>/dev/null
