/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  telegraf --test 2>/dev/null | grep -q 'metrics_failed=0,metrics_succeeded=6'
