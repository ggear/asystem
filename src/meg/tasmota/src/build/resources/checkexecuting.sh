/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf -m 5 http://localhost:80/ >/dev/null
