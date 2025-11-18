/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  vernemq chkconfig >/dev/null 2>&1 &&
  vernemq ping >/dev/null 2>&1
