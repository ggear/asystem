/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(grep -c ERROR /etc/letsencrypt/logs/letsencrypt.log)" -eq 0 ]
