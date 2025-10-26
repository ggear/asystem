OUTPUT="$(telegraf --test 2>/dev/null)" &&
  [ "$(grep -c 'metrics_succeeded=6,metrics_failed=0' <<<"${OUTPUT}")" -eq 1 ] &&
  telegraf --once >/dev/null 2>&1
