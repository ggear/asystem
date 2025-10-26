OUTPUT="$(telegraf --test 2>/dev/null)" &&
  [ "$(grep -c '^> > digitemp,host=macmini-may,metric=temperature,run_code=0 metrics_failed=0,metrics_succeeded=3' <<<"${OUTPUT}")" -eq 1 ] &&
  telegraf --once >/dev/null 2>&1
